/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// [FORK] work-item-types — property value types rewritten for custom properties
/**
 * A single custom property value. Scalars: text/url/email/file as strings,
 * decimals as strings, datetimes as ISO strings, options/relations as ids,
 * booleans as booleans.
 */
export type TIssuePropertyValue = string | boolean | null;

/**
 * Per-issue custom property values, keyed by property id. Each property maps to
 * a list of values (single-element for scalar properties, multiple for
 * multi-valued ones).
 */
export type TIssuePropertyValues = Record<string, TIssuePropertyValue[]>;

export type TIssuePropertyValueErrors = Record<string, string | undefined>;
