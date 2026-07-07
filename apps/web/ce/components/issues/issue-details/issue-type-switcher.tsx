/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// [FORK] work-item-types
import { useEffect } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { ChevronDown } from "lucide-react";
import useSWR from "swr";
// plane imports
import { Logo } from "@plane/propel/emoji-icon-picker";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { EIssueServiceType } from "@plane/types";
import { CustomSearchSelect } from "@plane/ui";
// components
import { IdentifierText } from "@/components/issues/issue-detail/identifier-text";
// store hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssueTypes } from "@/hooks/store/use-issue-types";
import { useProject } from "@/hooks/store/use-project";
// services
import { IssueTypeService } from "@/services/issue-type.service";
// plane web components
import { IssueIdentifier } from "@/plane-web/components/issues/issue-details/issue-identifier";

const issueTypeService = new IssueTypeService();

export type TIssueTypeSwitcherProps = {
  issueId: string;
  disabled: boolean;
};

export const IssueTypeSwitcher = observer(function IssueTypeSwitcher(props: TIssueTypeSwitcherProps) {
  // [FORK] work-item-types
  const { issueId, disabled } = props;
  // router
  const { workspaceSlug: routeWorkspaceSlug } = useParams();
  const workspaceSlug = routeWorkspaceSlug?.toString() ?? "";
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  // [FORK] work-item-types
  const { getProjectIdentifierById, getProjectById } = useProject();
  const {
    fetchProjectIssueTypes,
    getProjectIssueTypes,
    getProjectIssueTypeIds,
    getIssueTypeById,
    isIssueTypeEnabledForProject,
  } = useIssueTypes();
  // derived values
  const issue = getIssueById(issueId);
  // [FORK] work-item-types
  const projectId = issue?.project_id ?? null;
  const isEnabled = isIssueTypeEnabledForProject(projectId);
  const isEpicEnabled = !!(projectId && getProjectById(projectId)?.is_epic_enabled);
  const hasFetched = getProjectIssueTypeIds(projectId) !== undefined;

  // [FORK] work-item-types — read the project's epic type so the switcher can
  // convert a work item to/from an epic. SWR dedupes across all switchers.
  const { data: epicType } = useSWR(
    isEpicEnabled && workspaceSlug && projectId ? `DEFAULT_EPIC_TYPE_${workspaceSlug}_${projectId}` : null,
    isEpicEnabled && workspaceSlug && projectId
      ? () => issueTypeService.fetchDefaultEpicType(workspaceSlug, projectId)
      : null
  );

  // [FORK] work-item-types — route by the CURRENT type (robust across conversions):
  // an epic (type === the epic type) is served by the epics API, not /issues/ (404).
  const isEpicItem = epicType?.id ? issue?.type_id === epicType.id : !!issue?.is_epic;
  const { updateIssue } = useIssueDetail(isEpicItem ? EIssueServiceType.EPICS : EIssueServiceType.ISSUES);

  useEffect(() => {
    if (isEnabled && workspaceSlug && projectId && !hasFetched) {
      void fetchProjectIssueTypes(workspaceSlug, projectId);
    }
  }, [isEnabled, workspaceSlug, projectId, hasFetched, fetchProjectIssueTypes]);

  if (!issue || !projectId) return <></>;

  const issueTypes = getProjectIssueTypes(projectId, true) ?? [];

  // Feature off / no types / read-only — render the plain identifier (icon + PROJ-123).
  if (!isEnabled || disabled || (issueTypes.length === 0 && !epicType)) {
    return <IssueIdentifier issueId={issueId} projectId={projectId} size="md" enableClickToCopyIdentifier />;
  }

  // [FORK] work-item-types — the epic type is excluded from the regular type list;
  // append it so a work item can be converted to (or away from) an epic.
  const typeOptions = [...issueTypes];
  if (epicType && !typeOptions.some((type) => type.id === epicType.id)) typeOptions.push(epicType);

  const selected = isEpicItem ? epicType : issue.type_id ? getIssueTypeById(issue.type_id) : undefined;
  const options = typeOptions.map((issueType) => ({
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
              <span className="text-11 text-tertiary">{selected?.name ?? "Type"}</span>
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
