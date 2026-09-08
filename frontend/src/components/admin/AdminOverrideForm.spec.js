import { mount, RouterLinkStub } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AdminOverrideForm from "./AdminOverrideForm.vue";

function mountForm(mode) {
  return mount(AdminOverrideForm, {
    global: { stubs: { RouterLink: RouterLinkStub } },
    props: {
      mode,
      title: `${mode} override`,
      description: "Override assignment",
      submitLabel: "Submit override",
    },
  });
}

describe("AdminOverrideForm", () => {
  it.each(["manual", "replacement"])("requires a reason for %s overrides", async (mode) => {
    const wrapper = mountForm(mode);
    await wrapper.get(`input[name="${mode}-availability-id"]`).setValue("4");
    await wrapper.get(`input[name="${mode}-application-id"]`).setValue("5");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.text()).toContain("Reason is required.");
    expect(wrapper.emitted("submit")).toBeUndefined();
  });

  it("emits normalized override values after validation", async () => {
    const wrapper = mountForm("manual");
    await wrapper.get('input[name="manual-availability-id"]').setValue("4");
    await wrapper.get('input[name="manual-application-id"]').setValue("5");
    await wrapper.get('textarea[name="manual-reason"]').setValue("  Exception approved  ");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("submit")[0]).toEqual([
      { availabilityId: 4, applicationId: 5, reason: "Exception approved" },
    ]);
  });

  it("shows employee ID guidance for replacement overrides", () => {
    const wrapper = mountForm("replacement");

    expect(wrapper.text()).toContain("Use Employee ID when no waiting request exists after assignment.");
    expect(wrapper.find('input[name="replacement-applicant-id"]').exists()).toBe(true);
  });

  it("explains override IDs and audit reason", () => {
    const wrapper = mountForm("replacement");

    expect(wrapper.text()).toContain("Find references first: open Requests");
    expect(wrapper.text()).toContain("Request ID uses an existing request");
    expect(wrapper.text()).toContain("Reason is required and appears in audit history");
  });

  it("links to reference lists without leaving entered values and describes the offer field", () => {
    const wrapper = mountForm("manual");
    const links = wrapper.findAllComponents(RouterLinkStub);
    expect(links.map((link) => link.props("to"))).toEqual(["/admin/parking-applications", "/admin/reservations"]);
    for (const link of links) expect(link.attributes("target")).toBe("_blank");
    const input = wrapper.get('input[name="manual-availability-id"]');
    expect(wrapper.get(`#${input.attributes("aria-describedby")}`).text()).toContain("Offer #");
  });

  it("emits applicant ID replacement values after validation", async () => {
    const wrapper = mountForm("replacement");
    await wrapper.get('input[name="replacement-availability-id"]').setValue("4");
    await wrapper.get('input[name="replacement-applicant-id"]').setValue("9");
    await wrapper.get('textarea[name="replacement-reason"]').setValue("  Replace by applicant  ");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("submit")[0]).toEqual([
      { availabilityId: 4, applicantId: 9, reason: "Replace by applicant" },
    ]);
  });

  it("requires exactly one replacement selector", async () => {
    const wrapper = mountForm("replacement");
    await wrapper.get('input[name="replacement-availability-id"]').setValue("4");
    await wrapper.get('input[name="replacement-application-id"]').setValue("5");
    await wrapper.get('input[name="replacement-applicant-id"]').setValue("9");
    await wrapper.get('textarea[name="replacement-reason"]').setValue("Replacement reason");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.text()).toContain("Enter either a request ID or an employee ID.");
    expect(wrapper.emitted("submit")).toBeUndefined();
  });

  it("requires a replacement selector", async () => {
    const wrapper = mountForm("replacement");
    await wrapper.get('input[name="replacement-availability-id"]').setValue("4");
    await wrapper.get('textarea[name="replacement-reason"]').setValue("Replacement reason");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.text()).toContain("Enter either a request ID or an employee ID.");
    expect(wrapper.emitted("submit")).toBeUndefined();
  });
});
