"""ASCII art mascots for orchestrator CLI."""

from enum import Enum


class MascotPose(str, Enum):
    """Available mascot poses."""

    HAPPY = "happy"
    THINKING = "thinking"
    WAVING = "waving"
    SLEEPING = "sleeping"


class SealMascot:
    """Seal mascot with multiple poses."""

    HAPPY = """
      ,-~~~-.
    ,'       `.
   /  °     °  \\
  |     <      |
   \\   ~~~   /
    `._____.,'
   ~~~~~~~~~~~~
"""

    THINKING = """
      ,-~~~-.
    ,'       `.
   /  °     °  \\
  |     ...    |
   \\   ~~~   /
    `._____.,'
   ~~~~~~~~~~~~
"""

    WAVING = """
      ,-~~~-.  ~
    ,'       `.
   /  °     °  \\
  |     <      |
   \\   ~~~   /
    `._____.,'
   ~~~~~~~~~~~~
"""

    SLEEPING = """
      ,-~~~-.
    ,'       `.
   /  -     -  \\
  |     <      |
   \\   ~~~   /
    `._____.,'
   ~~~~~~~~~~~~  zzz
"""

    @classmethod
    def get_pose(cls, pose: MascotPose = MascotPose.HAPPY) -> str:
        """Get mascot ASCII art for specific pose.

        Args:
            pose: Desired mascot pose

        Returns:
            ASCII art string
        """
        pose_map = {
            MascotPose.HAPPY: cls.HAPPY,
            MascotPose.THINKING: cls.THINKING,
            MascotPose.WAVING: cls.WAVING,
            MascotPose.SLEEPING: cls.SLEEPING,
        }
        return pose_map.get(pose, cls.HAPPY)

    @classmethod
    def get_colored_pose(
        cls,
        pose: MascotPose = MascotPose.HAPPY,
        color: str = "cyan"
    ) -> str:
        """Get mascot with Rich color markup.

        Args:
            pose: Desired mascot pose
            color: Rich color tag (cyan, yellow, green, etc.)

        Returns:
            Colored ASCII art string
        """
        art = cls.get_pose(pose)
        return f"[{color}]{art}[/{color}]"
