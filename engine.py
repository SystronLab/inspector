"""Evidence-only registration rules with conservative multi-UE correlation."""
import copy
import re
import time
from pdu import track_pdu
from failure_rules import match_failure
from datetime import datetime, timedelta

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
STAMP = re.compile(r'\b(\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\b')
IDS = {'ranUeNgapId': r'RAN_UE_NGAP_ID\[(\d+)\]',
       'amfUeNgapId': r'AMF_UE_NGAP_ID\[(\d+)\]', 'tac': r'TAC\[(\d+)\]',
       'cellId': r'CellID\[([^\]]+)\]', 'suci': r'\[(suci-[^\]\s]+)\]',
       'imsi': r'\[(imsi-\d+)(?=[:\]])'}
DIAGNOSTIC_DEFAULTS = {
    'lastSuccessfulStage': None, 'failureStage': None, 'failureReason': None,
    'protocolCause': None, 'diagnosisConfidence': None, 'failureEvidence': None,
    'failedAt': None,
}
NETWORK_FUNCTIONS = {'amf': 'AMF', 'gmm': 'AMF', 'ausf': 'AUSF',
                     'udm': 'UDM', 'smf': 'SMF'}


class Inspector:
    def __init__(self, year=None, timeout=30):
        self.year = year or datetime.now().year
        self.timeout = timeout
        self.attempts = []
        self.events = []
        self.seen = set()
        self.lines = 0
        self.clocks = {}
        self.uncorrelated = []

    @property
    def active(self):
        return any(self.is_active(record) for record in self.attempts)

    @staticmethod
    def is_active(record):
        return record['state'] in ('UE_DETECTED', 'REGISTRATION_IN_PROGRESS')

    def unresolved(self, stamp, raw, reason):
        self.uncorrelated.append({'timestamp': stamp.isoformat(timespec='milliseconds'),
                                  'rawEvidence': raw, 'reason': reason})

    @staticmethod
    def observe_network_function(record, component):
        """Record only a component from evidence correlated to this attempt."""
        network_function = NETWORK_FUNCTIONS.get(component)
        if network_function and network_function not in record['networkFunctions']:
            record['networkFunctions'].append(network_function)

    def correlate(self, identifiers, candidates, allow_enrichment=False):
        # Known identity / AMF ID outrank RAN ID (RAN IDs can be reused).
        keys = [k for k in ('imsi', 'suci', 'amfUeNgapId', 'ranUeNgapId') if k in identifiers]
        compatible = [r for r in candidates if all(
            r[k] is None or r[k] == identifiers[k] for k in keys)]
        for key in keys:
            matches = [r for r in compatible if r[key] == identifiers[key]]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                compatible = matches
        if allow_enrichment and len(compatible) == 1:
            return compatible[0]
        return None

    def latest_identities(self):
        ids = {group['latestSessionId'] for group in self.ues()}
        return [r for r in self.attempts if r['sessionId'] in ids]

    def ues(self):
        aliases = {}
        for record in self.attempts:
            if record['suci'] and record['imsi']:
                aliases.setdefault(record['suci'], set()).add(record['imsi'])
        groups = {}
        for record in self.attempts:
            known = aliases.get(record['suci'], set())
            resolved = next(iter(known)) if len(known) == 1 else None
            identity = record['imsi'] or resolved or record['suci'] or record['sessionId']
            group = groups.setdefault(identity, {'identity': identity, 'sessionIds': []})
            group.update(latestSessionId=record['sessionId'], state=record['state'],
                         imsi=record['imsi'] or resolved, suci=record['suci'])
            group['sessionIds'].append(record['sessionId'])
        return copy.deepcopy(list(groups.values()))

    def snapshot(self):
        return copy.deepcopy(self.attempts[-1]) if self.attempts else {
            'sessionId': None, 'state': 'WAITING', 'registrationStatus': 'WAITING',
            **dict.fromkeys(IDS), 'startedAt': None, 'completedAt': None,
            'durationMs': None, **DIAGNOSTIC_DEFAULTS,
            'deregistrationRequestedAt': None, 'networkFunctions': [],
            'pduSessions': [], 'events': []}

    def event(self, kind, stamp, raw, timestamp_source='log', record=None, pdu=None):
        record = record if record is not None else self.attempts[-1]
        event = {'type': kind, 'timestamp': stamp.isoformat(timespec='milliseconds'),
                 'timestampSource': timestamp_source, 'sessionId': record['sessionId'],
                 'state': record['state'], 'registrationStatus': record['registrationStatus'],
                 'identifiers': {key: record[key] for key in IDS}, 'rawEvidence': raw}
        if kind == 'REGISTRATION_FAILED':
            event.update({key: copy.deepcopy(record[key]) for key in DIAGNOSTIC_DEFAULTS})
            event['durationMs'] = record['durationMs']
        if pdu is not None:
            event['pduSession'] = {k: v for k, v in pdu.items() if k != 'events'}
            pdu['events'].append(copy.deepcopy(event))
        record['events'].append(event)
        self.events.append(event)

    def expire(self, stamp=None, clock=None):
        for record in self.attempts:
            if not self.is_active(record):
                continue
            start = datetime.fromisoformat(record['startedAt'])
            elapsed = ((stamp - start).total_seconds() if stamp is not None else
                       (time.monotonic() if clock is None else clock) - self.clocks[record['sessionId']])
            if elapsed >= self.timeout:
                requested = record['lastSuccessfulStage'] == 'REGISTRATION_REQUEST_RECEIVED'
                self.fail(start + timedelta(seconds=self.timeout),
                          'AFTER_REGISTRATION_REQUEST' if requested else 'NGAP_NAS',
                          ('Registration did not complete before timeout' if requested else
                           'No Registration request observed before timeout'),
                          'STAGE_LEVEL', None, 'timer', record, 'registration_timeout')

    def fail(self, stamp, stage, reason, confidence, raw, source, record, rule_name,
             component=None, severity=None, cause=None, identifiers=None):
        evidence = None if raw is None else {
            'rawLogLine': raw, 'timestamp': stamp.isoformat(timespec='milliseconds'),
            'component': component, 'severity': severity, 'matchedRule': rule_name,
            'identifiers': copy.deepcopy(identifiers or {}),
            'extractedIdentity': next((identifiers[k] for k in ('imsi', 'suci', 'amfUeNgapId', 'ranUeNgapId')
                                      if identifiers and k in identifiers), None),
            'extractedCause': cause,
        }
        record.update(state='FAILED', registrationStatus='FAILED', failureStage=stage,
                      failureReason=reason, protocolCause=cause,
                      diagnosisConfidence=confidence, failureEvidence=evidence,
                      failedAt=stamp.isoformat(timespec='milliseconds'),
                      durationMs=round((stamp - datetime.fromisoformat(record['startedAt'])).total_seconds() * 1000))
        self.event('REGISTRATION_FAILED', stamp, raw, source, record)

    def feed(self, raw, clock=None):
        self.lines += 1
        raw = raw.rstrip('\r\n')
        if raw in self.seen:
            return
        self.seen.add(raw)
        line = ANSI.sub('', raw)
        match = STAMP.search(line)
        source = 'log' if match else 'receipt'
        try:
            stamp = (datetime.strptime(f'{self.year}/{match[1]}', '%Y/%m/%d %H:%M:%S.%f')
                     if match else datetime.now())
        except ValueError:
            return
        # Log time advances replay deadlines even for noise, but noise cannot create a session.
        if match:
            self.expire(stamp=stamp)
        module = re.search(r'\[(amf|gmm|smf|ausf|udm)\]', line, re.I)
        if not module:
            return
        identifiers = {}
        failure_rule = cause = None
        for key, pattern in IDS.items():
            found = re.search(pattern, line)
            if found:
                identifiers[key] = int(found[1]) if key in ('ranUeNgapId', 'amfUeNgapId', 'tac') else found[1]
        component = module[1].lower()
        severity_match = re.search(r'\]\s+(TRACE|DEBUG|INFO|WARNING|WARN|ERROR|FATAL):', line, re.I)
        severity = severity_match[1].upper() if severity_match else None
        if track_pdu(self, component, line, identifiers, stamp, raw, source):
            return
        if component == 'smf':
            return
        if re.search(r'\bDeregistration\b', line, re.I):
            if re.search(r'\bDeregistration request\b', line, re.I):
                candidates = self.latest_identities()
                record = self.correlate(identifiers, candidates, allow_enrichment=True)
                if record is not None and record['state'] == 'REGISTERED':
                    record.update(identifiers)
                    record['state'] = 'DEREGISTERED'
                    record['deregistrationRequestedAt'] = stamp.isoformat(timespec='milliseconds')
                    self.event('DEREGISTRATION_REQUESTED', stamp, raw, source, record)
                elif record is None:
                    self.unresolved(stamp, raw, 'Deregistration has no unique matching UE')
            return
        initial = bool(re.search(r'\bInitialUEMessage\b', line))
        if initial:
            record = {'sessionId': f'registration-{len(self.attempts) + 1}',
                      'state': 'UE_DETECTED', 'registrationStatus': 'IN_PROGRESS',
                      **dict.fromkeys(IDS), 'startedAt': stamp.isoformat(timespec='milliseconds'),
                      'completedAt': None, 'durationMs': None, **DIAGNOSTIC_DEFAULTS,
                      'deregistrationRequestedAt': None, 'networkFunctions': [],
                      'pduSessions': [], 'events': []}
            self.attempts.append(record)
            self.clocks[record['sessionId']] = time.monotonic() if clock is None else clock
            record.update(identifiers)
            record['lastSuccessfulStage'] = 'INITIAL_UE_MESSAGE'
            self.event('INITIAL_UE_MESSAGE', stamp, raw, source, record)
        else:
            requested = re.search(r'\bRegistration request\b', line, re.I)
            completed = re.search(r'\bRegistration complete\b', line, re.I)
            failure_rule, cause = match_failure(component, line)
            # Only actual context/identity messages may enrich a registration.
            enrichment = re.search(r'RAN_UE_NGAP_ID|AMF_UE_NGAP_ID|\bSUCI\b', line)
            if not (requested or completed or failure_rule or enrichment):
                return
            candidates = [r for r in self.attempts if self.is_active(r)]
            if not candidates and not (requested or completed or failure_rule):
                return
            record = self.correlate(identifiers, candidates, allow_enrichment=True)
            if record is None:
                self.unresolved(stamp, raw, 'Registration evidence has no unique compatible active attempt')
                return
            record.update(identifiers)
        self.observe_network_function(record, component)
        if any(k in identifiers for k in ('ranUeNgapId', 'amfUeNgapId', 'tac', 'cellId')):
            self.event('UE_CONTEXT_IDENTIFIED', stamp, raw, source, record)
        if any(k in identifiers for k in ('suci', 'imsi')):
            self.event('UE_IDENTITY_RESOLVED', stamp, raw, source, record)
        if re.search(r'\bRegistration request\b', line, re.I):
            record['state'] = 'REGISTRATION_IN_PROGRESS'
            record['lastSuccessfulStage'] = 'REGISTRATION_REQUEST_RECEIVED'
            self.event('REGISTRATION_REQUESTED', stamp, raw, source, record)
        elif re.search(r'\bRegistration complete\b', line, re.I):
            record.update(state='REGISTERED', registrationStatus='SUCCESS',
                          lastSuccessfulStage='REGISTRATION_COMPLETE_RECEIVED',
                          completedAt=stamp.isoformat(timespec='milliseconds'),
                          durationMs=round((stamp - datetime.fromisoformat(record['startedAt'])).total_seconds() * 1000))
            self.event('REGISTRATION_COMPLETED', stamp, raw, source, record)
        elif failure_rule:
            self.fail(stamp, failure_rule['failure_stage'], failure_rule['reason'],
                      failure_rule['confidence'], raw, source, record,
                      failure_rule['name'], component, severity, cause, identifiers)
