<template>
  <details class="audit-decision">
    <summary>Review decision details</summary>
    <div class="audit-decision__content">
      <section v-for="(detail, index) in overviewDetails" :key="`overview-${index}`" class="audit-decision__section">
        <div class="audit-decision__section-heading">
          <h3>{{ actionLabel(detail) }}</h3>
          <StatusBadge :status="detail.action || detail.assignment_method || auditLog.trigger_source" />
        </div>
        <dl class="audit-decision__facts">
          <div v-if="reasonFor(detail)"><dt>Reason</dt><dd>{{ reasonFor(detail) }}</dd></div>
          <div v-if="actorId(detail)">
            <dt>Acted by</dt>
            <dd><PersonCell :fallback-id="actorId(detail)" show-reference :user="userById(actorId(detail))" /></dd>
          </div>
          <div v-if="detail.previous_user_id">
            <dt>Previous reservation holder</dt>
            <dd><PersonCell :fallback-id="detail.previous_user_id" show-reference :user="userById(detail.previous_user_id)" /></dd>
          </div>
          <div v-if="detail.selected_user_id || auditLog.selected_user_id">
            <dt>Selected employee</dt>
            <dd><PersonCell :fallback-id="detail.selected_user_id || auditLog.selected_user_id" show-reference :user="userById(detail.selected_user_id || auditLog.selected_user_id)" /></dd>
          </div>
          <div v-if="detail.selection_basis || detail.replacement_selection_basis">
            <dt>Selection basis</dt>
            <dd>{{ getStatusLabel(detail.replacement_selection_basis || detail.selection_basis) }}</dd>
          </div>
        </dl>
        <p v-if="referenceSummary(detail)" class="audit-decision__references">{{ referenceSummary(detail) }}</p>
      </section>

      <section v-if="rankedRequests.length" class="audit-decision__section">
        <h3>Ranked requests</h3>
        <ol class="audit-ranked-list">
          <li v-for="(request, index) in rankedRequests" :key="request.application_id || index">
            <span class="audit-ranked-list__rank">{{ request.final_rank_position || index + 1 }}</span>
            <div class="audit-ranked-list__person">
              <PersonCell :fallback-id="request.applicant_id" :user="userById(request.applicant_id)" />
              <small class="data-table__reference">Request #{{ request.application_id || "unknown" }}</small>
            </div>
            <div class="audit-ranked-list__priority">
              <span>{{ prioritySummary(request) }}</span>
              <small v-if="request.application_created_at"><DateTimeDisplay :value="request.application_created_at" /></small>
            </div>
            <StatusBadge :status="request.selected ? 'selected' : 'rejected'" />
          </li>
        </ol>
      </section>

      <section v-if="rejectedRequestIds.length" class="audit-decision__section">
        <h3>Requests not selected</h3>
        <ul class="audit-rejected-list">
          <li v-for="requestId in rejectedRequestIds" :key="requestId">
            <div>
              <strong>Request #{{ requestId }}</strong>
              <PersonCell
                v-if="candidateByRequestId(requestId)?.applicant_id"
                :fallback-id="candidateByRequestId(requestId).applicant_id"
                :user="userById(candidateByRequestId(requestId).applicant_id)"
              />
            </div>
            <StatusBadge status="rejected" />
          </li>
        </ul>
      </section>

      <p v-if="!hasStructuredDetails" class="audit-decision__fallback">
        This audit entry uses an older or custom detail format. Open Technical details for the complete recorded payload.
      </p>

      <JsonDetailsViewer summary="Technical details" :value="technicalDetails" />
    </div>
  </details>
</template>

<script setup>
import { computed } from "vue";

import JsonDetailsViewer from "@/components/admin/JsonDetailsViewer.vue";
import DateTimeDisplay from "@/components/common/DateTimeDisplay.vue";
import PersonCell from "@/components/common/PersonCell.vue";
import StatusBadge from "@/components/common/StatusBadge.vue";
import { getStatusLabel } from "@/utils/display";

const props = defineProps({
  auditLog: {
    type: Object,
    required: true,
  },
  usersById: {
    type: Object,
    default: () => ({}),
  },
});

const details = computed(() => (
  Array.isArray(props.auditLog.ranking_details)
    ? props.auditLog.ranking_details.filter((detail) => detail && typeof detail === "object" && !Array.isArray(detail))
    : []
));

const rankedRequests = computed(() => details.value.filter((detail) => (
  detail.action === "candidate_ranking"
  || detail.final_rank_position != null
  || (detail.application_id != null && (detail.applicant_id != null || detail.selected != null))
)));

const overviewDetails = computed(() => details.value.filter((detail) => (
  !rankedRequests.value.includes(detail) && [
    detail.action,
    detail.assignment_method,
    detail.override_reason,
    detail.reason,
    detail.admin_user_id,
    detail.actor_user_id,
    detail.previous_user_id,
    detail.selected_user_id,
  ].some((value) => value !== undefined && value !== null)
)));

const rejectedRequestIds = computed(() => (
  Array.isArray(props.auditLog.rejected_application_ids)
    ? props.auditLog.rejected_application_ids
    : []
));
const hasStructuredDetails = computed(() => (
  overviewDetails.value.length > 0 || rankedRequests.value.length > 0 || rejectedRequestIds.value.length > 0
));
const technicalDetails = computed(() => ({
  ranking_details: props.auditLog.ranking_details,
  rejected_application_ids: props.auditLog.rejected_application_ids,
}));

function userById(userId) {
  return props.usersById[userId] || null;
}

function candidateByRequestId(requestId) {
  return rankedRequests.value.find((detail) => detail.application_id === requestId);
}

function actionLabel(detail) {
  return getStatusLabel(detail.action || detail.assignment_method || props.auditLog.trigger_source);
}

function reasonFor(detail) {
  return detail.override_reason || detail.reason || null;
}

function actorId(detail) {
  return detail.admin_user_id || detail.actor_user_id || detail.owner_user_id || null;
}

function prioritySummary(detail) {
  const parts = [];
  if (detail.team_priority_active) {
    parts.push(detail.is_same_team_as_owner ? "Same-team priority" : "Outside owner team");
  } else {
    parts.push("Standard ordering");
  }
  if (Number.isInteger(detail.recent_win_count)) {
    parts.push(`${detail.recent_win_count} recent ${detail.recent_win_count === 1 ? "reservation" : "reservations"}`);
  }
  if (detail.is_over_soft_limit) parts.push("above fairness soft limit");
  return parts.join(" · ");
}

function referenceSummary(detail) {
  const references = [
    ["Previous reservation", detail.previous_reservation_id],
    ["Previous request", detail.previous_application_id],
    ["Selected request", detail.selected_application_id],
    ["New reservation", detail.new_reservation_id],
  ].filter(([, value]) => value);
  return references.map(([label, value]) => `${label} #${value}`).join(" · ");
}
</script>
