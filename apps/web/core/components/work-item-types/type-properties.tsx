/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Plus, Trash2, X } from "lucide-react";
// plane imports
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { EIssuePropertyType } from "@plane/types";
import type { TIssueProperty } from "@plane/types";
import { Button, Input, ToggleSwitch } from "@plane/ui";
// hooks
import { useIssueProperties } from "@/hooks/store/use-issue-properties";

type TProps = {
  workspaceSlug: string;
  projectId: string;
  typeId: string;
  isAdmin: boolean;
};

// Property types offered in the settings UI.
const PROPERTY_TYPE_OPTIONS: { value: EIssuePropertyType; label: string }[] = [
  { value: EIssuePropertyType.TEXT, label: "Text" },
  { value: EIssuePropertyType.DECIMAL, label: "Number" },
  { value: EIssuePropertyType.BOOLEAN, label: "Boolean" },
  { value: EIssuePropertyType.DATETIME, label: "Date" },
  { value: EIssuePropertyType.URL, label: "URL" },
  { value: EIssuePropertyType.EMAIL, label: "Email" },
  { value: EIssuePropertyType.OPTION, label: "Dropdown" },
];

const slugify = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]/g, "");

/** Inline manager to add options to an OPTION-typed property. */
const OptionsManager = observer(function OptionsManager(props: {
  workspaceSlug: string;
  projectId: string;
  property: TIssueProperty;
  isAdmin: boolean;
}) {
  const { workspaceSlug, projectId, property, isAdmin } = props;
  const { getPropertyOptions, createOption, deleteOption } = useIssueProperties();
  const [name, setName] = useState("");

  const options = getPropertyOptions(property.id);

  const handleAdd = async () => {
    if (!name.trim()) return;
    try {
      await createOption(workspaceSlug, projectId, property.id, { name: name.trim() });
      setName("");
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Could not add the option." });
    }
  };

  return (
    <div className="mt-2 flex flex-col gap-1.5 pl-4">
      {options.map((option) => (
        <div key={option.id} className="flex items-center justify-between text-13">
          <span className="text-secondary">{option.name}</span>
          {isAdmin && (
            <button
              type="button"
              onClick={() => deleteOption(workspaceSlug, projectId, property.id, option.id)}
              className="hover:text-danger-strong text-tertiary"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>
      ))}
      {isAdmin && (
        <div className="flex items-center gap-2">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="Add option…"
            className="h-7 text-13"
          />
          <Button variant="neutral-primary" size="sm" onClick={handleAdd} disabled={!name.trim()}>
            Add
          </Button>
        </div>
      )}
    </div>
  );
});

/**
 * Lists and manages the custom properties of a single work item type.
 */
export const WorkItemTypeProperties = observer(function WorkItemTypeProperties(props: TProps) {
  const { workspaceSlug, projectId, typeId, isAdmin } = props;
  const { getTypeProperties, createProperty, deleteProperty } = useIssueProperties();
  // add-form state
  const [isAdding, setIsAdding] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [propertyType, setPropertyType] = useState<EIssuePropertyType>(EIssuePropertyType.TEXT);
  const [isRequired, setIsRequired] = useState(false);
  const [isMulti, setIsMulti] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const properties = getTypeProperties(projectId, typeId) ?? [];

  const resetForm = () => {
    setDisplayName("");
    setPropertyType(EIssuePropertyType.TEXT);
    setIsRequired(false);
    setIsMulti(false);
    setIsAdding(false);
  };

  const handleCreate = async () => {
    if (!displayName.trim()) return;
    setIsSubmitting(true);
    try {
      await createProperty(workspaceSlug, projectId, typeId, {
        name: slugify(displayName) || `prop_${Date.now()}`,
        display_name: displayName.trim(),
        property_type: propertyType,
        is_required: isRequired,
        is_multi: isMulti,
      });
      resetForm();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Could not create the property." });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mt-2 border-t border-subtle-1 pt-3">
      <div className="flex flex-col gap-2">
        {properties.map((property) => (
          <div key={property.id} className="rounded border border-subtle-1 bg-layer-1 px-3 py-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-13">
                <span className="font-medium text-primary">{property.display_name}</span>
                <span className="rounded bg-layer-3 px-1.5 py-0.5 text-11 text-tertiary">
                  {PROPERTY_TYPE_OPTIONS.find((o) => o.value === property.property_type)?.label ??
                    property.property_type}
                </span>
                {property.is_required && (
                  <span className="rounded bg-layer-3 px-1.5 py-0.5 text-11 text-tertiary">Required</span>
                )}
                {property.is_multi && (
                  <span className="rounded bg-layer-3 px-1.5 py-0.5 text-11 text-tertiary">Multi</span>
                )}
              </div>
              {isAdmin && (
                <button
                  type="button"
                  onClick={() => deleteProperty(workspaceSlug, projectId, typeId, property.id)}
                  className="hover:text-danger-strong text-tertiary"
                >
                  <Trash2 className="size-3.5" />
                </button>
              )}
            </div>
            {property.property_type === EIssuePropertyType.OPTION && (
              <OptionsManager
                workspaceSlug={workspaceSlug}
                projectId={projectId}
                property={property}
                isAdmin={isAdmin}
              />
            )}
          </div>
        ))}
        {properties.length === 0 && !isAdding && (
          <span className="text-13 text-tertiary">No custom properties on this type yet.</span>
        )}
      </div>

      {isAdmin &&
        (isAdding ? (
          <div className="mt-2 flex flex-col gap-2 rounded border border-subtle-1 bg-layer-1 p-3">
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Property name"
              className="h-8 text-13"
            />
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={propertyType}
                onChange={(e) => setPropertyType(e.target.value as EIssuePropertyType)}
                className="h-8 rounded border border-subtle-1 bg-layer-2 px-2 text-13 text-primary"
              >
                {PROPERTY_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <span className="flex items-center gap-1.5 text-13 text-secondary">
                <ToggleSwitch value={isRequired} onChange={setIsRequired} size="sm" />
                Required
              </span>
              <span className="flex items-center gap-1.5 text-13 text-secondary">
                <ToggleSwitch value={isMulti} onChange={setIsMulti} size="sm" />
                Multi
              </span>
            </div>
            <div className="flex items-center justify-end gap-2">
              <Button variant="neutral-primary" size="sm" onClick={resetForm}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleCreate}
                loading={isSubmitting}
                disabled={!displayName.trim() || isSubmitting}
              >
                Add property
              </Button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsAdding(true)}
            className="mt-2 flex items-center gap-1 text-13 text-tertiary hover:text-secondary"
          >
            <Plus className="size-3.5" /> Add property
          </button>
        ))}
    </div>
  );
});
