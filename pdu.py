"""PDU evidence visible in this Open5GS build; no inferred establishment success."""
import re


def track_pdu(engine, module, line, identifiers, stamp, raw, source):
    removed = module == 'smf' and 'Removed Session: UE IMSI:' in line
    address = module == 'smf' and 'UE SUPI[' in line and 'IPv4[' in line
    context = module == 'gmm' and 'UE SUPI[' in line and 'smContextRef[' in line
    modify = module == 'amf' and '/nsmf-pdusession/v1/sm-contexts/{smContextRef}/modify' in line
    release = module == 'amf' and 'Release SM Context [state:' in line
    if not any((removed, address, context, modify, release)):
        return False
    imsi = identifiers.get('imsi')
    # PDU evidence must explicitly name a UE. Never fall back to the most recent UE.
    owners = [r for r in engine.latest_identities() if imsi and r['imsi'] == imsi]
    if len(owners) != 1:
        engine.unresolved(stamp, raw, 'PDU evidence has no uniquely identified registration')
        return True
    owner = owners[0]
    engine.observe_network_function(owner, module)
    dnn_match = re.search(r'DNN:?\[([^\]]+)\]', line)
    dnn = dnn_match[1] if dnn_match else None
    psi = None
    if removed and dnn:
        parts = dnn.rsplit(':', 1)
        if len(parts) == 2 and parts[1].isdigit():
            dnn, psi = parts[0], int(parts[1])
    compound = re.search(r'\[imsi-\d+:(\d+)(?=[:\]])', line)
    if compound:
        psi = int(compound[1])
    ipv4 = re.search(r'IPv4:?\[([^\]]*)\]', line)
    ipv6 = re.search(r'IPv6:?\[([^\]]*)\]', line)
    attrs = {'dnn': dnn, 'pduSessionId': psi,
             'ipv4': ipv4[1] or None if ipv4 else None,
             'ipv6': ipv6[1] or None if ipv6 else None}
    slice_match = re.search(r'S_NSSAI\[SST:(\d+) SD:([^\]]+)\]', line)
    if slice_match:
        attrs.update(sst=int(slice_match[1]), sd=slice_match[2])
    if removed or release:
        # Release may arrive after the same UE starts another registration. Search
        # existing sessions across attempts rather than assigning it to the latest.
        matching = [(r, s) for r in engine.attempts if r['imsi'] == imsi
                    for s in r['pduSessions'] if s['state'] != 'RELEASED' and all(
                        value is None or s.get(key) is None or s[key] == value
                        for key, value in attrs.items())]
        if len(matching) > 1:
            engine.unresolved(stamp, raw, 'Release matches multiple PDU sessions across attempts')
            return True
        if matching:
            owner = matching[0][0]
    candidates = [s for s in owner['pduSessions'] if s['state'] != 'RELEASED' and all(
        value is None or s.get(key) is None or s[key] == value for key, value in attrs.items())]
    exact = [s for s in candidates if psi is not None and s['pduSessionId'] == psi and all(
            v is None or s.get(k) is None or s[k] == v for k, v in attrs.items())]
    if exact:
        candidates = exact
    if len(candidates) > 1:
        engine.unresolved(stamp, raw, 'PDU evidence matches multiple sessions for this UE')
        return True
    session = candidates[0] if candidates else None
    if session is None:
        # A release/modify after removal must not resurrect a historical session.
        historical = [s for s in owner['pduSessions'] if psi is not None and s['pduSessionId'] == psi and all(
            v is None or s.get(k) is None or s[k] == v for k, v in attrs.items())]
        if (release or modify or removed) and historical:
            session = historical[-1]
        else:
            session = {'id': f"{owner['sessionId']}-pdu-{len(owner['pduSessions']) + 1}",
                       'pduSessionId': None, 'dnn': None, 'ipv4': None, 'ipv6': None,
                       'sst': None, 'sd': None, 'state': 'CONTEXT_OBSERVED',
                       'firstObservedAt': stamp.isoformat(timespec='milliseconds'),
                       'ipAssignedAt': None, 'releasedAt': None, 'events': []}
            owner['pduSessions'].append(session)
    session.update({k: v for k, v in attrs.items() if v is not None})
    kind = 'PDU_CONTEXT_OBSERVED'
    if address:
        kind = 'PDU_ADDRESS_OBSERVED'
        if session['ipv4'] or session['ipv6']:
            session.update(state='IP_ASSIGNED', ipAssignedAt=stamp.isoformat(timespec='milliseconds'))
    elif removed:
        kind = 'PDU_SESSION_REMOVED'
        session.update(state='RELEASED', releasedAt=stamp.isoformat(timespec='milliseconds'))
    elif modify:
        kind = 'PDU_CONTEXT_IDENTIFIED'
    elif release:
        kind = 'PDU_SM_CONTEXT_RELEASE_OBSERVED'
    engine.event(kind, stamp, raw, source, owner, session)
    return True
