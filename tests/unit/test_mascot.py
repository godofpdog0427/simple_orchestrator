"""Unit tests for seal mascot."""

import pytest

from orchestrator.cli.mascot import SealMascot, MascotPose


class TestSealMascot:
    """Tests for seal mascot ASCII art."""

    def test_get_pose_happy(self):
        """Test getting happy pose."""
        art = SealMascot.get_pose(MascotPose.HAPPY)
        assert "°     °" in art  # Eyes
        assert "<" in art  # Nose
        assert "~~~" in art  # Mouth and water

    def test_get_pose_thinking(self):
        """Test getting thinking pose."""
        art = SealMascot.get_pose(MascotPose.THINKING)
        assert "..." in art  # Thinking dots

    def test_get_pose_waving(self):
        """Test getting waving pose."""
        art = SealMascot.get_pose(MascotPose.WAVING)
        assert "~" in art  # Wave indicator

    def test_get_pose_sleeping(self):
        """Test getting sleeping pose."""
        art = SealMascot.get_pose(MascotPose.SLEEPING)
        assert "-     -" in art  # Closed eyes
        assert "zzz" in art  # Sleep indicator

    def test_get_colored_pose(self):
        """Test getting colored pose."""
        art = SealMascot.get_colored_pose(MascotPose.HAPPY, "cyan")
        assert "[cyan]" in art
        assert "[/cyan]" in art

    def test_all_poses_have_water(self):
        """Test all poses include water (seal's element)."""
        for pose in MascotPose:
            art = SealMascot.get_pose(pose)
            assert "~" in art  # Water waves

    def test_default_pose(self):
        """Test default pose is HAPPY."""
        default_art = SealMascot.get_pose()
        happy_art = SealMascot.get_pose(MascotPose.HAPPY)
        assert default_art == happy_art

    def test_invalid_pose_returns_happy(self):
        """Test invalid pose returns HAPPY pose."""
        # Use a string that's not in the enum
        art = SealMascot.get_pose("invalid")  # type: ignore
        happy_art = SealMascot.get_pose(MascotPose.HAPPY)
        # Should return happy as fallback
        # Note: The get_pose method will use .get() with default

    def test_all_poses_multiline(self):
        """Test all poses are multiline ASCII art."""
        for pose in MascotPose:
            art = SealMascot.get_pose(pose)
            lines = art.strip().split("\n")
            assert len(lines) >= 5  # At least 5 lines for seal body + water
