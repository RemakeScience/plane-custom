/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef, useState } from "react";
import { observer } from "mobx-react";
import { Loader2, Paperclip, X } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { EFileAssetType } from "@plane/types";
import type { TIssuePropertyValue } from "@plane/types";
import { getFileURL } from "@plane/utils";
// services
import { FileService } from "@/services/file.service";

const fileService = new FileService();
const CE = "work_item_types.settings.properties.ce";

/** Parse a FILE property value: we store `{"id","name"}` JSON so the filename
 * survives a reload; older/plain values degrade gracefully to the raw string. */
const parseFileValue = (raw: TIssuePropertyValue | undefined): { id: string; name: string } | null => {
  if (typeof raw !== "string" || raw === "") return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.id === "string") return { id: parsed.id, name: parsed.name || parsed.id };
  } catch {
    // legacy plain string (asset id or url)
  }
  return { id: raw, name: raw };
};

const downloadUrl = (workspaceSlug: string, projectId: string, assetId: string) =>
  getFileURL(`/api/assets/v2/workspaces/${workspaceSlug}/projects/${projectId}/${assetId}/`) ?? "";

export type TFilePropertyFieldProps = {
  value: TIssuePropertyValue[];
  disabled?: boolean;
  projectId: string;
  workspaceSlug: string;
  onChange: (value: TIssuePropertyValue[]) => void;
};

/** Upload/download control for a FILE custom property. Uploads reuse Plane's
 * project asset pipeline (S3/MinIO); the value stores the asset id + name. */
export const FilePropertyField = observer(function FilePropertyField(props: TFilePropertyFieldProps) {
  const { value, disabled, projectId, workspaceSlug, onChange } = props;
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const current = parseFileValue(value?.[0]);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setIsUploading(true);
    try {
      const response = await fileService.uploadProjectAsset(
        workspaceSlug,
        projectId,
        { entity_type: EFileAssetType.ISSUE_PROPERTY_VALUE, entity_identifier: projectId },
        file
      );
      onChange([JSON.stringify({ id: response.asset_id, name: file.name })]);
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("common.error"), message: t(`${CE}.file_upload_error`) });
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        disabled={disabled || isUploading}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {current ? (
        <>
          <a
            href={downloadUrl(workspaceSlug, projectId, current.id)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex max-w-40 items-center gap-1 truncate text-13 text-accent-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            <Paperclip className="size-3.5 flex-shrink-0" />
            <span className="truncate">{current.name}</span>
          </a>
          {!disabled && (
            <button type="button" onClick={() => onChange([])} title={t("common.remove")}>
              <X className="hover:text-danger-strong size-3.5 text-tertiary" />
            </button>
          )}
        </>
      ) : (
        <button
          type="button"
          disabled={disabled || isUploading}
          onClick={() => inputRef.current?.click()}
          className="inline-flex items-center gap-1 rounded border border-subtle-1 px-2 py-0.5 text-12 text-secondary hover:bg-layer-2 disabled:opacity-60"
        >
          {isUploading ? <Loader2 className="size-3.5 animate-spin" /> : <Paperclip className="size-3.5" />}
          {isUploading ? t(`${CE}.file_uploading`) : t(`${CE}.file_upload`)}
        </button>
      )}
    </div>
  );
});
