/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Pencil, Trash2 } from "lucide-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { setPromiseToast, setToast, TOAST_TYPE } from "@plane/propel/toast";
import type { TIssueType } from "@plane/types";
import { Loader, ToggleSwitch } from "@plane/ui";
// components
import { SettingsHeading } from "@/components/settings/heading";
// hooks
import { useIssueTypes } from "@/hooks/store/use-issue-types";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { CreateUpdateIssueTypeModal } from "./create-update-modal";
import { DeleteIssueTypeModal } from "./delete-modal";

export const WorkItemTypesSettingsRoot = observer(function WorkItemTypesSettingsRoot() {
  // router
  const { workspaceSlug: routeWorkspaceSlug, projectId: routeProjectId } = useParams();
  const workspaceSlug = routeWorkspaceSlug?.toString() ?? "";
  const projectId = routeProjectId?.toString() ?? "";
  // store hooks
  const { getProjectById, updateProject } = useProject();
  const { allowPermissions } = useUserPermissions();
  const {
    fetchProjectIssueTypes,
    getProjectIssueTypes,
    getProjectIssueTypeIds,
    markAsDefault,
    enableIssueTypes,
    enableEpics,
  } = useIssueTypes();
  // states
  const [isTogglingFeature, setIsTogglingFeature] = useState(false);
  const [isTogglingEpics, setIsTogglingEpics] = useState(false);
  const [createUpdateModal, setCreateUpdateModal] = useState<{ isOpen: boolean; data: TIssueType | null }>({
    isOpen: false,
    data: null,
  });
  const [deleteData, setDeleteData] = useState<TIssueType | null>(null);
  // derived values
  const project = getProjectById(projectId);
  const isEnabled = Boolean(project?.is_issue_type_enabled);
  const isEpicEnabled = Boolean(project?.is_epic_enabled);
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);
  const issueTypes = getProjectIssueTypes(projectId);
  const hasFetched = getProjectIssueTypeIds(projectId) !== undefined;

  useEffect(() => {
    if (isEnabled && workspaceSlug && projectId && !hasFetched) {
      void fetchProjectIssueTypes(workspaceSlug, projectId);
    }
  }, [isEnabled, workspaceSlug, projectId, hasFetched, fetchProjectIssueTypes]);

  const handleToggleFeature = async () => {
    if (!isAdmin || !workspaceSlug || !projectId) return;
    setIsTogglingFeature(true);
    try {
      await updateProject(workspaceSlug, projectId, { is_issue_type_enabled: !isEnabled });
      // when enabling, ensure a default type exists (and backfill untyped work items)
      if (!isEnabled) await enableIssueTypes(workspaceSlug, projectId);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Could not update the feature. Please try again." });
    } finally {
      setIsTogglingFeature(false);
    }
  };

  const handleToggleEpics = async () => {
    if (!isAdmin || !workspaceSlug || !projectId) return;
    setIsTogglingEpics(true);
    try {
      await updateProject(workspaceSlug, projectId, { is_epic_enabled: !isEpicEnabled });
      // when enabling, ensure the project's Epic type exists
      if (!isEpicEnabled) await enableEpics(workspaceSlug, projectId);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Could not update Epics. Please try again." });
    } finally {
      setIsTogglingEpics(false);
    }
  };

  const handleMarkAsDefault = (issueType: TIssueType) => {
    if (issueType.is_default) return;
    const promise = markAsDefault(workspaceSlug, projectId, issueType.id);
    setPromiseToast(promise, {
      loading: "Setting default type...",
      success: { title: "Success!", message: () => `${issueType.name} is now the default type.` },
      error: { title: "Error!", message: () => "Could not set the default type." },
    });
  };

  return (
    <div className="size-full">
      <SettingsHeading
        title="Work Item Types"
        description="Classify work items with custom types (Bug, Feature, Task…) so your team can tell them apart at a glance."
        control={
          isEnabled && isAdmin ? (
            <Button variant="primary" size="sm" onClick={() => setCreateUpdateModal({ isOpen: true, data: null })}>
              Add type
            </Button>
          ) : undefined
        }
      />

      <div className="mt-4 flex items-center justify-between rounded-md border border-subtle-1 bg-layer-2 px-4 py-3">
        <div className="flex flex-col">
          <span className="text-13 font-medium text-primary">Enable work item types</span>
          <span className="text-13 text-tertiary">
            Turn this on to create and assign types to work items in this project.
          </span>
        </div>
        <ToggleSwitch value={isEnabled} onChange={handleToggleFeature} disabled={!isAdmin || isTogglingFeature} />
      </div>

      <div className="mt-3 flex items-center justify-between rounded-md border border-subtle-1 bg-layer-2 px-4 py-3">
        <div className="flex flex-col">
          <span className="text-13 font-medium text-primary">Enable epics</span>
          <span className="text-13 text-tertiary">
            Epics are large work items that group related work items across cycles and modules.
          </span>
        </div>
        <ToggleSwitch value={isEpicEnabled} onChange={handleToggleEpics} disabled={!isAdmin || isTogglingEpics} />
      </div>

      {isEnabled && (
        <div className="mt-6">
          {!hasFetched ? (
            <Loader className="space-y-3">
              <Loader.Item height="52px" />
              <Loader.Item height="52px" />
            </Loader>
          ) : (
            <div className="flex flex-col gap-2">
              {(issueTypes ?? []).map((issueType) => (
                <div
                  key={issueType.id}
                  className="flex items-center justify-between rounded-md border border-subtle-1 bg-layer-2 px-4 py-2.5"
                >
                  <div className="flex items-center gap-2 truncate">
                    <span className="flex size-7 flex-shrink-0 items-center justify-center rounded bg-layer-3">
                      {issueType.logo_props?.in_use ? (
                        <Logo logo={issueType.logo_props} size={16} />
                      ) : (
                        <span className="text-13 text-tertiary">{issueType.name.charAt(0).toUpperCase()}</span>
                      )}
                    </span>
                    <div className="flex flex-col truncate">
                      <span className="flex items-center gap-2 text-13 font-medium text-primary">
                        {issueType.name}
                        {issueType.is_default && (
                          <span className="rounded bg-layer-3 px-1.5 py-0.5 text-11 text-tertiary">Default</span>
                        )}
                        {!issueType.is_active && (
                          <span className="rounded bg-layer-3 px-1.5 py-0.5 text-11 text-tertiary">Inactive</span>
                        )}
                      </span>
                      {issueType.description && (
                        <span className="truncate text-13 text-tertiary">{issueType.description}</span>
                      )}
                    </div>
                  </div>

                  {isAdmin && (
                    <div className="flex flex-shrink-0 items-center gap-1">
                      {!issueType.is_default && (
                        <button
                          type="button"
                          onClick={() => handleMarkAsDefault(issueType)}
                          className="rounded px-2 py-1 text-13 text-tertiary hover:bg-layer-3 hover:text-secondary"
                        >
                          Set default
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setCreateUpdateModal({ isOpen: true, data: issueType })}
                        className="rounded p-1.5 text-tertiary hover:bg-layer-3 hover:text-secondary"
                      >
                        <Pencil className="size-4" />
                      </button>
                      <button
                        type="button"
                        disabled={issueType.is_default}
                        onClick={() => setDeleteData(issueType)}
                        className="hover:text-danger-strong rounded p-1.5 text-tertiary hover:bg-layer-3 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {issueTypes?.length === 0 && (
                <div className="rounded-md border border-dashed border-subtle-1 px-4 py-8 text-center text-13 text-tertiary">
                  No work item types yet. Create your first one.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <CreateUpdateIssueTypeModal
        isOpen={createUpdateModal.isOpen}
        data={createUpdateModal.data}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        onClose={() => setCreateUpdateModal({ isOpen: false, data: null })}
      />
      <DeleteIssueTypeModal
        isOpen={Boolean(deleteData)}
        data={deleteData}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        onClose={() => setDeleteData(null)}
      />
    </div>
  );
});
