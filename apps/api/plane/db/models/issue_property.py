# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models
from django.db.models import Q

# Module imports
from .project import ProjectBaseModel


class PropertyTypeEnum(models.TextChoices):
    """Supported custom property value types."""

    TEXT = "TEXT", "Text"
    DECIMAL = "DECIMAL", "Decimal"
    OPTION = "OPTION", "Option"
    BOOLEAN = "BOOLEAN", "Boolean"
    DATETIME = "DATETIME", "Datetime"
    RELATION = "RELATION", "Relation"
    URL = "URL", "URL"
    EMAIL = "EMAIL", "Email"
    FILE = "FILE", "File"


class RelationTypeEnum(models.TextChoices):
    """Target of a RELATION property."""

    ISSUE = "ISSUE", "Issue"
    MEMBER = "MEMBER", "Member"


class IssueProperty(ProjectBaseModel):
    """A custom property definition attached to an issue type.

    Mirrors the paid-edition ``issue_properties`` schema so a future import
    stays possible. Options (for OPTION properties) live in
    ``IssuePropertyOption`` and per-issue values in ``IssuePropertyValue``.
    """

    issue_type = models.ForeignKey("db.IssueType", on_delete=models.CASCADE, related_name="properties")
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    logo_props = models.JSONField(default=dict)
    property_type = models.CharField(max_length=20, choices=PropertyTypeEnum.choices)
    # Only meaningful when property_type == RELATION.
    relation_type = models.CharField(max_length=20, choices=RelationTypeEnum.choices, null=True, blank=True)
    is_required = models.BooleanField(default=False)
    is_multi = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    default_value = models.JSONField(default=list, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    sort_order = models.FloatField(default=65535)
    external_source = models.CharField(max_length=255, null=True, blank=True)
    external_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Issue Property"
        verbose_name_plural = "Issue Properties"
        db_table = "issue_properties"
        ordering = ("sort_order",)

    def __str__(self):
        return f"{self.issue_type.name} - {self.display_name}"


class IssuePropertyOption(ProjectBaseModel):
    """A selectable option for an OPTION-typed property."""

    property = models.ForeignKey("db.IssueProperty", on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    logo_props = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    sort_order = models.FloatField(default=65535)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    external_source = models.CharField(max_length=255, null=True, blank=True)
    external_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Issue Property Option"
        verbose_name_plural = "Issue Property Options"
        db_table = "issue_property_options"
        ordering = ("sort_order",)
        constraints = [
            models.UniqueConstraint(
                fields=["property", "name"],
                condition=Q(deleted_at__isnull=True),
                name="issue_property_option_unique_name_when_deleted_at_null",
            )
        ]

    def __str__(self):
        return f"{self.property.display_name} - {self.name}"


class IssuePropertyValue(ProjectBaseModel):
    """A value of a custom property for a single issue.

    Typed columns keep the value queryable and EE-schema compatible. A single
    (issue, property) pair maps to one row for scalar properties, or several
    rows for multi-valued properties (one per value).
    """

    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="property_values")
    property = models.ForeignKey("db.IssueProperty", on_delete=models.CASCADE, related_name="values")
    value_text = models.TextField(null=True, blank=True)
    value_boolean = models.BooleanField(default=False)
    value_decimal = models.DecimalField(max_digits=25, decimal_places=8, null=True, blank=True)
    value_datetime = models.DateTimeField(null=True, blank=True)
    value_uuid = models.UUIDField(null=True, blank=True)
    value_option = models.ForeignKey(
        "db.IssuePropertyOption",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="property_values",
    )
    external_source = models.CharField(max_length=255, null=True, blank=True)
    external_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Issue Property Value"
        verbose_name_plural = "Issue Property Values"
        db_table = "issue_property_values"
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.issue_id} - {self.property.display_name}"
