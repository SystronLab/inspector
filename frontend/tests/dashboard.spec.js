// Synthetic UI fixtures only; these are not captured UE logs.
import { test, expect } from "@playwright/test";
const a = "imsi-001010123456780",
  b = "imsi-001010123456781";
function fixture() {
  const event = {
    type: "REGISTRATION_COMPLETED",
    timestamp: "2026-09-06T15:44:58.279",
    sessionId: "registration-1",
    state: "REGISTERED",
    timestampSource: "log",
    rawEvidence: "[gmm] Registration complete <img src=x onerror=alert(1)>",
  };
  const first = {
    sessionId: "registration-1",
    imsi: a,
    suci: "suci-test-a",
    state: "REGISTERED",
    registrationStatus: "SUCCESS",
    startedAt: "2026-09-06T15:44:57.741",
    completedAt: "2026-09-06T15:44:58.279",
    durationMs: 538,
    ranUeNgapId: 0,
    amfUeNgapId: 1,
    tac: 7,
    cellId: "0x66c000",
    networkFunctions: ["AMF", "SMF"],
    events: [event],
    pduSessions: [
      {
        id: "pdu-1",
        pduSessionId: 1,
        state: "IP_ASSIGNED",
        dnn: "internet",
        ipv4: "10.45.1.2",
        sst: 1,
        sd: "0xffffff",
        events: [],
      },
    ],
  };
  const second = {
    ...first,
    sessionId: "registration-2",
    imsi: b,
    suci: "suci-test-b",
    state: "DEREGISTERED",
    durationMs: 600,
    events: [],
    pduSessions: [],
  };
  return {
    health: {
      logSource: { connected: true, mode: "stdin", error: null },
      linesProcessed: 120,
      matchedEvents: 13,
      uncorrelatedLines: 1,
    },
    registrations: [first, second],
    ues: [
      {
        identity: a,
        imsi: a,
        suci: first.suci,
        state: first.state,
        sessionIds: [first.sessionId],
        latestSessionId: first.sessionId,
      },
      {
        identity: b,
        imsi: b,
        suci: second.suci,
        state: second.state,
        sessionIds: [second.sessionId],
        latestSessionId: second.sessionId,
      },
    ],
    registration: second,
    uncorrelated: [
      {
        timestamp: event.timestamp,
        reason: "Multiple compatible UEs",
        rawEvidence: "[gmm] Registration request",
      },
    ],
  };
}
async function mock(page, data, fail = () => false) {
  await page.route("**/api/*", (route) =>
    fail()
      ? route.fulfill({ status: 503, body: "Unavailable" })
      : route.fulfill({
          json: data[new URL(route.request().url()).pathname.split("/").at(-1)],
        }),
  );
}
test("switches UEs and displays their own PDU evidence", async ({ page }) => {
  await mock(page, fixture());
  await page.goto("");
  await expect(
    page.getByRole("heading", { name: b, exact: true }),
  ).toBeVisible();
  await page.getByRole("combobox", { name: "UE", exact: true }).selectOption(a);
  await expect(
    page.getByRole("heading", { name: a, exact: true }),
  ).toBeVisible();
  await expect(page.getByText("10.45.1.2", { exact: true })).toBeVisible();
  await expect(page.getByText("Network functions involved", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Log timestamp", { exact: true })).toHaveCount(0);
  await expect(page.getByText("0", { exact: true }).last()).toBeVisible();
  await expect(page.locator(".fields dd").first()).toHaveCSS("font-size", "16px");
  await expect(page.locator(".fields dd").first()).toHaveCSS("color", "rgb(17, 24, 39)");
  await expect(page.locator(".page-header")).toHaveCSS("width", "1280px");
  await expect(page.locator(".page-footer")).toHaveCSS("width", "1280px");
  await expect(page.getByRole("link", { name: "SYSTRON LAB" }).first()).toHaveAttribute("href", "https://systronlab.github.io/");
});
test("raw evidence is safe and stays expanded across polls", async ({
  page,
}) => {
  await mock(page, fixture());
  await page.goto("");
  await page.getByRole("combobox", { name: "UE", exact: true }).selectOption(a);
  await page.locator(".timeline-panel").getByText("View raw evidence", { exact: true }).click();
  await expect(page.locator(".timeline-panel pre")).toContainText("<img src=x");
  await expect(page.locator("pre img")).toHaveCount(0);
  await page.waitForTimeout(1200);
  await expect(page.locator(".timeline-panel details")).toHaveAttribute("open", "");
  await page
    .getByRole("textbox", { name: "Search events" })
    .fill("not-in-fixture");
  await expect(
    page.getByRole("heading", { name: "No matching events" }),
  ).toBeVisible();
});
test("keeps uncorrelated evidence out of the primary UI", async ({ page }) => {
  await mock(page, fixture());
  await page.goto("");
  await expect(page.getByText(/Uncorrelated evidence/)).toHaveCount(0);
  await expect(page.getByText("Multiple compatible UEs")).toHaveCount(0);
});
test("retains last data and reports polling failures", async ({ page }) => {
  let failed = false;
  await mock(page, fixture(), () => failed);
  await page.goto("");
  await expect(
    page.getByRole("heading", { name: b, exact: true }),
  ).toBeVisible();
  failed = true;
  await expect(page.getByRole("alert")).toContainText(
    "Inspector connection interrupted",
  );
  await expect(
    page.getByRole("heading", { name: b, exact: true }),
  ).toBeVisible();
  await expect(page.locator(".connection")).toHaveText("Disconnected");
});
test("empty state remains clear and mobile has no horizontal overflow", async ({
  page,
}) => {
  const data = fixture();
  data.registrations = [];
  data.ues = [];
  data.registration = {
    state: "WAITING",
    registrationStatus: "WAITING",
    events: [],
    pduSessions: [],
  };
  data.health.linesProcessed = 0;
  data.health.logSource.connected = false;
  await mock(page, data);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("");
  await expect(
    page.getByRole("heading", { name: "Waiting for UE detection" }),
  ).toBeVisible();
  await expect(
    page.getByText("Waiting for core logs", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("attempt selection persists when new data arrives", async ({ page }) => {
  const data = fixture();
  const history = {
    ...data.registrations[0],
    sessionId: "registration-3",
    durationMs: 700,
  };
  data.registrations.push(history);
  data.ues[0].sessionIds.push(history.sessionId);
  data.ues[0].latestSessionId = history.sessionId;
  await mock(page, data);
  await page.goto("");
  await page.getByRole("combobox", { name: "UE", exact: true }).selectOption(a);
  await page.getByLabel("Registration attempt").selectOption("registration-1");
  await page.waitForTimeout(1200);
  await expect(page.getByLabel("Registration attempt")).toHaveValue(
    "registration-1",
  );
  await expect(page.locator(".duration")).toContainText("538");
});

test("shows the evidence-backed failure diagnosis panel", async ({ page }) => {
  const data = fixture();
  const failed = {
    ...data.registrations[0],
    state: "FAILED",
    registrationStatus: "FAILED",
    lastSuccessfulStage: "REGISTRATION_REQUEST_RECEIVED",
    failureStage: "AUTHENTICATION",
    failureReason: "Authentication failed",
    protocolCause: null,
    diagnosisConfidence: "EXACT",
    durationMs: 742,
    failureEvidence: {
      rawLogLine: "[gmm] ERROR: Authentication failure",
      matchedRule: "authentication_failure",
    },
  };
  data.registrations = [failed];
  data.registration = failed;
  data.ues = [{ ...data.ues[0], state: "FAILED" }];
  await mock(page, data);
  await page.goto("");
  const panel = page.getByRole("alert");
  await expect(panel).toContainText("Registration failed");
  await expect(panel).toContainText("AUTHENTICATION");
  await expect(panel).toContainText("REGISTRATION REQUEST RECEIVED");
  await expect(panel).toContainText("Not provided by core");
  await expect(panel).toContainText("742 ms");
  await panel.getByText("Evidence from Open5GS", { exact: true }).click();
  await expect(panel.locator("pre")).toContainText("Authentication failure");
});
