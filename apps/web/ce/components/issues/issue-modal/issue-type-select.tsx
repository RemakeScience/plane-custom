/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { ChevronDown } from "lucide-react";
import { Controller } from "react-hook-form";
import type { Control } from "react-hook-form";
// plane imports
import type { EditorRefApi } from "@plane/editor";
import { Logo } from "@plane/propel/emoji-icon-picker";
import type { TBulkIssueProperties, TIssue } from "@plane/types";
import { CustomSearchSelect } from "@plane/ui";
// hooks
import { useIssueTypes } from "@/hooks/store/use-issue-types";

export type TIssueFields = TIssue & TBulkIssueProperties;

export type TIssueTypeDropdownVariant = "xs" | "sm";

export type TIssueTypeSelectProps<T extends Partial<TIssueFields>> = {
  control: Control<T>;
  projectId: string | null;
  editorRef?: React.MutableRefObject<EditorRefApi | null>;
  disabled?: boolean;
  variant?: TIssueTypeDropdownVariant;
  placeholder?: string;
  isRequired?: boolean;
  renderChevron?: boolean;
  dropDownContainerClassName?: string;
  showMandatoryFieldInfo?: boolean; // Show info about mandatory fields
  handleFormChange?: () => void;
};

export const IssueTypeSelect = observer(function IssueTypeSelect<T extends Partial<TIssueFields>>(
  props: TIssueTypeSelectProps<T>
) {
  const { control, projectId, disabled = false, placeholder = "Type", renderChevron = false, handleFormChange } = props;
  // router
  const { workspaceSlug: routeWorkspaceSlug } = useParams();
  const workspaceSlug = routeWorkspaceSlug?.toString() ?? "";
  // store hooks
  const {
    fetchProjectIssueTypes,
    getProjectIssueTypes,
    getProjectIssueTypeIds,
    getIssueTypeById,
    isIssueTypeEnabledForProject,
  } = useIssueTypes();
  // derived values
  const isEnabled = isIssueTypeEnabledForProject(projectId);
  const hasFetched = getProjectIssueTypeIds(projectId) !== undefined;

  useEffect(() => {
    if (isEnabled && workspaceSlug && projectId && !hasFetched) {
      void fetchProjectIssueTypes(workspaceSlug, projectId);
    }
  }, [isEnabled, workspaceSlug, projectId, hasFetched, fetchProjectIssueTypes]);

  // The feature is off for this project — render nothing (matches the community stub behaviour).
  if (!isEnabled || !projectId) return null;

  const issueTypes = getProjectIssueTypes(projectId, true) ?? [];
  if (issueTypes.length === 0) return null;

  const options = issueTypes.map((issueType) => ({
    value: issueType.id,
    query: issueType.name,
    content: (
      <div className="flex items-center gap-2">
        {issueType.logo_props?.in_use && <Logo logo={issueType.logo_props} size={14} />}
        <span className="truncate">{issueType.name}</span>
      </div>
    ),
  }));

  return (
    <Controller
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      control={control as unknown as Control<any>}
      name="type_id"
      render={({ field: { value, onChange } }) => {
        const selected = value ? getIssueTypeById(value) : undefined;
        return (
          <CustomSearchSelect
            value={value ?? null}
            options={options}
            onChange={(val: string) => {
              onChange(val);
              handleFormChange?.();
            }}
            disabled={disabled}
            className="h-7"
            customButton={
              <div className="flex h-7 items-center gap-1 rounded border-[0.5px] border-subtle-1 bg-layer-2 px-2 text-13 text-secondary">
                {selected?.logo_props?.in_use && <Logo logo={selected.logo_props} size={14} />}
                <span className="truncate">{selected?.name ?? placeholder}</span>
                {renderChevron && <ChevronDown className="size-3 text-tertiary" />}
              </div>
            }
          />
        );
      }}
    />
  );
});
