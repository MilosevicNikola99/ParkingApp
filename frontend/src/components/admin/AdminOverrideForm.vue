<template>
  <section class="admin-action-panel" :aria-labelledby="`${mode}-override-title`">
    <div class="workspace-section__header">
      <p class="admin-action-panel__eyebrow">{{ isReplacementMode ? "Correct active reservation" : "Assign open parking offer" }}</p>
      <h2 :id="`${mode}-override-title`">{{ title }}</h2>
      <p>{{ description }}</p>
    </div>

    <div class="field-guide" aria-label="Override field guide">
      <p><strong>Find references first:</strong> open <RouterLink class="inline-link" to="/admin/parking-applications" target="_blank" rel="noopener">Requests</RouterLink> for the request and offer references, then <RouterLink class="inline-link" to="/admin/reservations" target="_blank" rel="noopener">Reservations</RouterLink> for the current assignment. Links open in a new tab so your entries stay here.</p>
      <p v-if="isReplacementMode"><strong>Request ID</strong> uses an existing request. <strong>Employee ID</strong> is for an employee who should replace the current holder when no waiting request exists.</p>
      <p v-else><strong>Request ID</strong> identifies the waiting request to assign.</p>
      <p><strong>Reason</strong> is required and appears in audit history.</p>
    </div>

    <form class="admin-form technical-id-form" :aria-busy="loading" @submit.prevent="submitForm">
      <p class="technical-id-form__heading">Technical identifiers</p>
      <BaseInput
        v-model="form.availabilityId"
        label="Availability ID"
        hint="Use the Offer # reference from Requests."
        min="1"
        :name="`${mode}-availability-id`"
        required
        step="1"
        type="number"
      />
      <BaseInput
        v-model="form.applicationId"
        label="Request ID"
        min="1"
        :name="`${mode}-application-id`"
        :required="!isReplacementMode"
        step="1"
        type="number"
      />
      <BaseInput
        v-if="isReplacementMode"
        v-model="form.applicantId"
        label="Employee ID"
        min="1"
        :name="`${mode}-applicant-id`"
        step="1"
        type="number"
      />
      <p v-if="isReplacementMode" class="form-helper">
        Use Employee ID when no waiting request exists after assignment. Enter either Request ID or Employee ID, not both.
      </p>
      <BaseTextarea
        v-model="form.reason"
        label="Reason"
        hint="Required. Explain why this assignment needs an exception; this is saved in audit history."
        :name="`${mode}-reason`"
        placeholder="Required audit reason"
      />
      <AlertMessage :message="validationError" />
      <slot name="feedback" />
      <div class="form-actions">
        <BaseButton :loading="loading" type="submit">{{ submitLabel }}</BaseButton>
      </div>
    </form>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import AlertMessage from "@/components/common/AlertMessage.vue";
import BaseButton from "@/components/common/BaseButton.vue";
import BaseInput from "@/components/common/BaseInput.vue";
import BaseTextarea from "@/components/common/BaseTextarea.vue";

const props = defineProps({
  mode: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    required: true,
  },
  submitLabel: {
    type: String,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["submit"]);
const isReplacementMode = computed(() => props.mode === "replacement");
const validationError = ref("");
const form = reactive({
  availabilityId: "",
  applicationId: "",
  applicantId: "",
  reason: "",
});

function parsePositiveId(value) {
  const parsedValue = Number(value);
  return Number.isInteger(parsedValue) && parsedValue >= 1 ? parsedValue : null;
}

function submitForm() {
  const availabilityId = parsePositiveId(form.availabilityId);
  const reason = form.reason.trim();

  if (availabilityId === null) {
    validationError.value = "Enter a valid availability ID.";
    return;
  }
  if (!reason) {
    validationError.value = "Reason is required.";
    return;
  }

  const hasApplicationId = form.applicationId.trim() !== "";
  const hasApplicantId = form.applicantId.trim() !== "";
  if (isReplacementMode.value) {
    if (hasApplicationId === hasApplicantId) {
      validationError.value = "Enter either a request ID or an employee ID.";
      return;
    }
    if (hasApplicationId) {
      const applicationId = parsePositiveId(form.applicationId);
      if (applicationId === null) {
        validationError.value = "Enter a valid request ID.";
        return;
      }

      validationError.value = "";
      emit("submit", { availabilityId, applicationId, reason });
      return;
    }

    const applicantId = parsePositiveId(form.applicantId);
    if (applicantId === null) {
      validationError.value = "Enter a valid employee ID.";
      return;
    }

    validationError.value = "";
    emit("submit", { availabilityId, applicantId, reason });
    return;
  }

  const applicationId = parsePositiveId(form.applicationId);
  if (applicationId === null) {
    validationError.value = "Enter a valid request ID.";
    return;
  }

  validationError.value = "";
  emit("submit", { availabilityId, applicationId, reason });
}
</script>
