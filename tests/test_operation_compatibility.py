from __future__ import annotations

from src.conflict_detector.core.models import ModifyOperation, RenameOperation, freeze_attrs
from src.conflict_detector.semantics.operation_compatibility import (
    operations_are_semantically_compatible,
    rewrite_operations_after_prior_renames,
)


def test_rename_and_modify_non_identity_attribute_are_compatible():
    rename = RenameOperation(
        target="public.users.email",
        new_name="email_address",
    )
    modify = ModifyOperation(
        target="public.users.email",
        delta=freeze_attrs({"nullable": True}),
    )

    result = operations_are_semantically_compatible(rename, modify)

    assert result.is_compatible is True


def test_rename_and_modify_identity_attribute_are_not_compatible():
    rename = RenameOperation(
        target="public.users.email",
        new_name="email_address",
    )
    modify = ModifyOperation(
        target="public.users.email",
        delta=freeze_attrs({"name": "other_name"}),
    )

    result = operations_are_semantically_compatible(rename, modify)

    assert result.is_compatible is False


def test_rewrite_modify_target_after_prior_rename():
    rename = RenameOperation(
        target="public.users.email",
        new_name="email_address",
    )
    modify = ModifyOperation(
        target="public.users.email",
        delta=freeze_attrs({"nullable": True}),
    )

    rewritten = rewrite_operations_after_prior_renames(
        operations=(modify,),
        prior_operations=(rename,),
    )

    assert len(rewritten) == 1
    assert isinstance(rewritten[0], ModifyOperation)
    assert rewritten[0].target == "public.users.email_address"
    assert dict(rewritten[0].delta)["nullable"] is True
