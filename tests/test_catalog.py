"""Tests for imx.catalog — loading task classes, profiles, and node descriptors."""
from pathlib import Path

from imx.catalog import (
    load_task_classes,
    load_profiles,
    load_node_descriptors,
    task_class_exists,
)

CATALOG = Path(__file__).parent.parent / "catalog"


# --- load_task_classes() ---

def test_load_task_classes_returns_at_least_5():
    classes = load_task_classes(CATALOG)
    assert len(classes) >= 5


def test_load_task_classes_returns_dict():
    classes = load_task_classes(CATALOG)
    assert isinstance(classes, dict)


# --- task_class_exists() ---

def test_task_class_exists_implementation():
    assert task_class_exists("implementation", CATALOG) is True


def test_task_class_exists_code_review():
    assert task_class_exists("code_review", CATALOG) is True


def test_task_class_exists_dotted_prefix_match():
    # implementation.bugfix may be defined exactly, but something invented is not
    # and must match via parent prefix lookup
    assert task_class_exists("implementation.something_invented", CATALOG) is True


def test_task_class_exists_implementation_bugfix():
    # This may match exactly or via prefix — either way it must be True
    assert task_class_exists("implementation.bugfix", CATALOG) is True


def test_task_class_exists_nonexistent():
    assert task_class_exists("nonexistent", CATALOG) is False


def test_task_class_exists_nonexistent_dotted():
    assert task_class_exists("nonexistent.subtask", CATALOG) is False


# --- load_profiles() ---

def test_load_profiles_returns_at_least_3():
    profiles = load_profiles(CATALOG)
    assert len(profiles) >= 3


def test_load_profiles_contains_economy():
    profiles = load_profiles(CATALOG)
    assert "economy" in profiles


def test_load_profiles_contains_balanced():
    profiles = load_profiles(CATALOG)
    assert "balanced" in profiles


def test_load_profiles_contains_deep():
    profiles = load_profiles(CATALOG)
    assert "deep" in profiles


def test_load_profiles_returns_capability_profile_objects():
    from imx.models import CapabilityProfile
    profiles = load_profiles(CATALOG)
    for profile in profiles.values():
        assert isinstance(profile, CapabilityProfile)


# --- load_node_descriptors() ---

def test_load_node_descriptors_returns_at_least_1():
    nodes = load_node_descriptors(CATALOG)
    assert len(nodes) >= 1


def test_load_node_descriptors_returns_node_descriptor_objects():
    from imx.models import NodeDescriptor
    nodes = load_node_descriptors(CATALOG)
    for node in nodes:
        assert isinstance(node, NodeDescriptor)


def test_load_node_descriptors_have_node_ids():
    nodes = load_node_descriptors(CATALOG)
    for node in nodes:
        assert node.node_id != ""
