/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { ChevronDown } from "lucide-react";
// plane imports
import { Logo } from "@plane/propel/emoji-icon-picker";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { CustomSearchSelect } from "@plane/ui";
// components
import { IdentifierText } from "@/components/issues/issue-detail/identifier-text";
// store hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssueTypes } from "@/hooks/store/use-issue-types";
import { useProject } from "@/hooks/store/use-project";
// plane web components
import { IssueIdentifier } from "@/plane-web/components/issues/issue-details/issue-identifier";

export type TIssueTypeSwitcherProps = {
  issueId: string;
  disabled: boolean;
};

export const IssueTypeSwitcher = observer(function IssueTypeSwitcher(props: TIssueTypeSwitcherProps) {
  const { issueId, disabled } = props;
  // router
  const { workspaceSlug: routeWorkspaceSlug } = useParams();
  const workspaceSlug = routeWorkspaceSlug?.toString() ?? "";
  // store hooks
  const {
    issue: { getIssueById },
    updateIssue,
  } = useIssueDetail();
  const { getProjectIdentifierById } = useProject();
  const {
    fetchProjectIssueTypes,
    getProjectIssueTypes,
    getProjectIssueTypeIds,
    getIssueTypeById,
    isIssueTypeEnabledForProject,
  } = useIssueTypes();
  // derived values
  const issue = getIssueById(issueId);
  const projectId = issue?.project_id ?? null;
  const isEnabled = isIssueTypeEnabledForProject(projectId);
  const hasFetched = getProjectIssueTypeIds(projectId) !== undefined;

  useEffect(() => {
    if (isEnabled && workspaceSlug && projectId && !hasFetched) {
      void fetchProjectIssueTypes(workspaceSlug, projectId);
    }
  }, [isEnabled, workspaceSlug, projectId, hasFetched, fetchProjectIssueTypes]);

  if (!issue || !projectId) return <></>;

  const issueTypes = getProjectIssueTypes(projectId, true) ?? [];

  // Feature off / no types / read-only — render the plain identifier (icon + PROJ-123).
  if (!isEnabled || disabled || issueTypes.length === 0) {
    return <IssueIdentifier issueId={issueId} projectId={projectId} size="md" enableClickToCopyIdentifier />;
  }

  const selected = issue.type_id ? getIssueTypeById(issue.type_id) : undefined;
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

  const handleChange = (typeId: string) => {
    updateIssue(workspaceSlug, projectId, issueId, { type_id: typeId }).catch(() => {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Could not update the work item type." });
    });
  };

  return (
    <div className="flex items-center gap-2">
      <CustomSearchSelect
        value={issue.type_id ?? null}
        options={options}
        onChange={handleChange}
        customButton={
          <span
            className="flex items-center gap-1 rounded border-[0.5px] border-subtle-1 bg-layer-2 px-1.5 py-1 hover:bg-layer-3"
            title={selected?.name ?? "Set type"}
          >
            {selected?.logo_props?.in_use ? (
              <Logo logo={selected.logo_props} size={14} />
            ) : (
              <span className="text-11 text-tertiary">Type</span>
            )}
            <ChevronDown className="size-3 text-tertiary" />
          </span>
        }
      />
      <IdentifierText
        identifier={`${getProjectIdentifierById(projectId)}-${issue.sequence_id}`}
        enableClickToCopyIdentifier
        size="md"
      />
    </div>
  );
});
