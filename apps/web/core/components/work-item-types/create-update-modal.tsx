/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Controller, useForm } from "react-hook-form";
// plane imports
import { Button } from "@plane/propel/button";
import { EmojiPicker, EmojiIconPickerTypes, Logo } from "@plane/propel/emoji-icon-picker";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TIssueType } from "@plane/types";
import { EModalPosition, EModalWidth, Input, ModalCore, ToggleSwitch } from "@plane/ui";
// hooks
import { useIssueTypes } from "@/hooks/store/use-issue-types";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  workspaceSlug: string;
  projectId: string;
  /** When provided the modal edits an existing type, otherwise it creates one. */
  data?: TIssueType | null;
};

type TFormValues = Pick<TIssueType, "name" | "description" | "is_active" | "logo_props">;

const DEFAULT_VALUES: TFormValues = {
  name: "",
  description: "",
  is_active: true,
  logo_props: undefined,
};

export const CreateUpdateIssueTypeModal = observer(function CreateUpdateIssueTypeModal(props: Props) {
  const { isOpen, onClose, workspaceSlug, projectId, data } = props;
  // store hooks
  const { createType, updateType } = useIssueTypes();
  // states
  const [isEmojiPickerOpen, setIsEmojiPickerOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // form
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TFormValues>({ defaultValues: DEFAULT_VALUES });

  useEffect(() => {
    if (!isOpen) return;
    reset(
      data
        ? { name: data.name, description: data.description, is_active: data.is_active, logo_props: data.logo_props }
        : DEFAULT_VALUES
    );
  }, [isOpen, data, reset]);

  const handleClose = () => {
    onClose();
    setIsEmojiPickerOpen(false);
  };

  const onSubmit = async (formData: TFormValues) => {
    setIsSubmitting(true);
    try {
      if (data) {
        await updateType(workspaceSlug, projectId, data.id, formData);
      } else {
        await createType(workspaceSlug, projectId, formData);
      }
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Success!",
        message: data ? "Work item type updated." : "Work item type created.",
      });
      handleClose();
    } catch (error) {
      const message = (error as { error?: string })?.error ?? "Something went wrong. Please try again.";
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={handleClose} position={EModalPosition.CENTER} width={EModalWidth.XL}>
      <form onSubmit={handleSubmit(onSubmit)} className="p-5">
        <h3 className="text-lg font-medium text-primary">{data ? "Edit work item type" : "New work item type"}</h3>

        <div className="mt-4 flex items-start gap-2">
          <Controller
            control={control}
            name="logo_props"
            render={({ field: { value, onChange } }) => (
              <EmojiPicker
                iconType="material"
                isOpen={isEmojiPickerOpen}
                handleToggle={setIsEmojiPickerOpen}
                className="flex items-center justify-center"
                buttonClassName="flex size-9 flex-shrink-0 items-center justify-center rounded-md border border-subtle-1 bg-layer-2"
                label={
                  value?.in_use ? <Logo logo={value} size={18} /> : <span className="text-13 text-tertiary">Icon</span>
                }
                // TODO: fix types (mirrors apps/web/core/components/project/form.tsx)
                onChange={(val: any) => {
                  if (val?.type === "emoji") onChange({ in_use: "emoji", emoji: { value: val.value } });
                  else if (val?.type === "icon") onChange({ in_use: "icon", icon: val.value });
                  setIsEmojiPickerOpen(false);
                }}
                defaultOpen={value?.in_use === "emoji" ? EmojiIconPickerTypes.EMOJI : EmojiIconPickerTypes.ICON}
              />
            )}
          />
          <div className="flex-grow">
            <Controller
              control={control}
              name="name"
              rules={{ required: "Name is required", maxLength: { value: 255, message: "Name is too long" } }}
              render={({ field: { value, onChange } }) => (
                <Input
                  value={value}
                  onChange={onChange}
                  placeholder="Type name (e.g. Bug, Feature)"
                  className="w-full"
                  hasError={Boolean(errors.name)}
                />
              )}
            />
            {errors.name && <span className="text-danger-strong text-13">{errors.name.message}</span>}
          </div>
        </div>

        <Controller
          control={control}
          name="description"
          render={({ field: { value, onChange } }) => (
            <textarea
              value={value}
              onChange={onChange}
              placeholder="Description (optional)"
              rows={3}
              className="placeholder-tertiary mt-3 w-full resize-none rounded-md border border-subtle-1 bg-layer-2 p-2 text-13 outline-none"
            />
          )}
        />

        <Controller
          control={control}
          name="is_active"
          render={({ field: { value, onChange } }) => (
            <div className="mt-3 flex items-center justify-between">
              <span className="text-13 text-secondary">Active</span>
              <ToggleSwitch value={Boolean(value)} onChange={onChange} />
            </div>
          )}
        />

        <div className="mt-5 flex items-center justify-end gap-2">
          <Button variant="tertiary" size="sm" onClick={handleClose} type="button">
            Cancel
          </Button>
          <Button variant="primary" size="sm" type="submit" loading={isSubmitting}>
            {data ? "Update" : "Create"}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});
