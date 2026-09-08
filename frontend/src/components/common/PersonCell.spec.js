import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import PersonCell from "./PersonCell.vue";

describe("PersonCell", () => {
  it("stacks a full name and email without parenthesized formatting", () => {
    const wrapper = mount(PersonCell, {
      props: {
        user: {
          id: 7,
          first_name: "Ada",
          last_name: "Admin",
          email: "ada.admin@example.com",
          username: "ada.admin",
        },
      },
    });

    expect(wrapper.get(".person-cell__name").text()).toBe("Ada Admin");
    expect(wrapper.get(".person-cell__email").text()).toBe("ada.admin@example.com");
    expect(wrapper.text()).not.toContain("Ada Admin (ada.admin@example.com)");
  });

  it("falls back through username, email, and technical reference", () => {
    expect(mount(PersonCell, { props: { user: { username: "operator" } } }).text()).toBe("operator");
    const emailOnly = mount(PersonCell, { props: { user: { email: "person@example.com" } } });
    expect(emailOnly.text()).toBe("person@example.com");
    expect(emailOnly.find(".person-cell__email").exists()).toBe(false);
    expect(mount(PersonCell, { props: { fallbackId: 42 } }).text()).toBe("User #42");
  });

  it("optionally shows username and a secondary user reference", () => {
    const wrapper = mount(PersonCell, {
      props: {
        fallbackId: 7,
        showReference: true,
        showUsername: true,
        user: { first_name: "Ada", last_name: "Admin", username: "ada.admin" },
      },
    });

    expect(wrapper.get(".person-cell__username").text()).toBe("@ada.admin");
    expect(wrapper.get(".person-cell__reference").text()).toBe("User #7");
  });
});
