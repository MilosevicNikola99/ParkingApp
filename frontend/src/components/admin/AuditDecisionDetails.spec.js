import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AuditDecisionDetails from "./AuditDecisionDetails.vue";

const usersById = {
  4: { id: 4, first_name: "Ada", last_name: "Admin", email: "ada@example.com" },
  7: { id: 7, first_name: "Erin", last_name: "Employee", email: "erin@example.com" },
  8: { id: 8, first_name: "Noah", last_name: "Notselected", email: "noah@example.com" },
};

function mountDetails(auditLog) {
  return mount(AuditDecisionDetails, { props: { auditLog, usersById } });
}

describe("AuditDecisionDetails", () => {
  it("renders ranked and not-selected requests as structured content", () => {
    const wrapper = mountDetails({
      trigger_source: "scheduled",
      selected_user_id: 7,
      rejected_application_ids: [22],
      ranking_details: [
        { action: "candidate_ranking", application_id: 21, applicant_id: 7, final_rank_position: 1, selected: true, team_priority_active: true, is_same_team_as_owner: true, recent_win_count: 0 },
        { action: "candidate_ranking", application_id: 22, applicant_id: 8, final_rank_position: 2, selected: false, team_priority_active: true, is_same_team_as_owner: false, recent_win_count: 1 },
      ],
    });

    expect(wrapper.text()).toContain("Ranked requests");
    expect(wrapper.text()).toContain("Erin Employee");
    expect(wrapper.text()).toContain("Same-team priority");
    expect(wrapper.text()).toContain("Requests not selected");
    expect(wrapper.text()).toContain("Request #22");
    expect(wrapper.text()).toContain("Not selected");
  });

  it("renders an override summary with actor, reason, previous user, and replacement", () => {
    const wrapper = mountDetails({
      trigger_source: "admin_override",
      selected_user_id: 7,
      rejected_application_ids: [],
      ranking_details: [{
        action: "replacement",
        admin_user_id: 4,
        override_reason: "Coverage correction",
        previous_user_id: 8,
        selected_user_id: 7,
        previous_reservation_id: 30,
        selected_application_id: 21,
      }],
    });

    expect(wrapper.text()).toContain("Replacement");
    expect(wrapper.text()).toContain("Coverage correction");
    expect(wrapper.text()).toContain("Ada Admin");
    expect(wrapper.text()).toContain("Previous reservation holder");
    expect(wrapper.text()).toContain("Erin Employee");
    expect(wrapper.text()).toContain("Previous reservation #30");
  });

  it("keeps raw JSON in collapsed technical details", () => {
    const wrapper = mountDetails({
      trigger_source: "system",
      selected_user_id: 7,
      rejected_application_ids: [],
      ranking_details: [{ action: "cancellation", reason: "Policy exception" }],
    });

    const technical = wrapper.findAll("details").find((details) => details.text().includes("Technical details"));
    expect(technical.attributes("open")).toBeUndefined();
    expect(technical.text()).toContain('"action": "cancellation"');
  });

  it("shows a friendly fallback for irregular payloads", () => {
    const wrapper = mountDetails({
      trigger_source: "system",
      selected_user_id: 7,
      rejected_application_ids: [],
      ranking_details: [{ unexpected: "legacy-value" }],
    });

    expect(wrapper.text()).toContain("older or custom detail format");
    expect(wrapper.text()).toContain("Technical details");
  });
});
