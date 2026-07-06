/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { X } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { EIssuePropertyRelationType } from "@plane/types";
import type { ISearchIssueResponse, TIssueProperty, TIssuePropertyValue } from "@plane/types";
// components
import { ExistingIssuesListModal } from "@/components/core/modals/existing-issues-list-modal";
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";

const CE = "work_item_types.settings.properties.ce";

export type TPropertyRelationFieldProps = {
  property: TIssueProperty;
  value: TIssuePropertyValue[];
  disabled?: boolean;
  projectId: string;
  workspaceSlug: string;
  onChange: (value: TIssuePropertyValue[]) => void;
};

const toStringIds = (value: TIssuePropertyValue[]): string[] =>
  value.filter((entry): entry is string => typeof entry === "string" && entry !== "");

/** Renders a RELATION custom property: a member picker or a work item picker. */
export const PropertyRelationField = observer(function PropertyRelationField(props: TPropertyRelationFieldProps) {
  const { property, value, disabled, projectId, workspaceSlug, onChange } = props;
  const { t } = useTranslation();
  const ids = toStringIds(value);
  // Cache the label of picked work items so we can render them without a fetch.
  const [issueLabels, setIssueLabels] = useState<Record<string, string>>({});
  const [isPickerOpen, setIsPickerOpen] = useState(false);

  if (property.relation_type === EIssuePropertyRelationType.MEMBER) {
    if (property.is_multi) {
      return (
        <MemberDropdown
          projectId={projectId}
          multiple
          value={ids}
          onChange={(next) => onChange(next)}
          disabled={disabled}
          placeholder={t(`${CE}.relation.select_members`)}
          buttonVariant="border-with-text"
        />
      );
    }
    return (
      <MemberDropdown
        projectId={projectId}
        multiple={false}
        value={ids[0] ?? null}
        onChange={(next) => onChange(next ? [next] : [])}
        disabled={disabled}
        placeholder={t(`${CE}.relation.select_member`)}
        buttonVariant="border-with-text"
      />
    );
  }

  // RELATION -> ISSUE
  const handleSubmit = async (selected: ISearchIssueResponse[]) => {
    setIssueLabels((prev) => {
      const next = { ...prev };
      selected.forEach((issue) => {
        next[issue.id] = `${issue.project__identifier}-${issue.sequence_id}`;
      });
      return next;
    });
    const selectedIds = selected.map((issue) => issue.id);
    onChange(property.is_multi ? Array.from(new Set([...ids, ...selectedIds])) : selectedIds.slice(0, 1));
    setIsPickerOpen(false);
  };

  return (
    <div className="flex flex-wrap items-center gap-1">
      {ids.map((id) => (
        <span key={id} className="inline-flex items-center gap-1 rounded bg-layer-2 px-2 py-0.5 text-12 text-primary">
          {issueLabels[id] ?? id.slice(0, 8)}
          {!disabled && (
            <button type="button" onClick={() => onChange(ids.filter((entry) => entry !== id))}>
              <X className="size-3 text-tertiary hover:text-primary" />
            </button>
          )}
        </span>
      ))}
      {!disabled && (
        <button
          type="button"
          onClick={() => setIsPickerOpen(true)}
          className="rounded border border-subtle-1 px-2 py-0.5 text-12 text-secondary hover:bg-layer-2"
        >
          {property.is_multi || ids.length === 0 ? t(`${CE}.relation.add_work_item`) : t(`${CE}.relation.change`)}
        </button>
      )}
      <ExistingIssuesListModal
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        isOpen={isPickerOpen}
        handleClose={() => setIsPickerOpen(false)}
        searchParams={{ target_date: undefined }}
        selectedWorkItemIds={ids}
        handleOnSubmit={handleSubmit}
      />
    </div>
  );
});
