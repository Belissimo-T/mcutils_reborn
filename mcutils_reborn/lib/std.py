from .. import Namespace
from ..commands import UniqueScoreboardObjective, Comment, Command, FunctionCall, LiteralCommand, UniqueTag
from .. import tools


def tag_remove_all(tag: UniqueTag | str) -> list[Command]:
    return [
        Comment("remove the temp tag from all entities"),
        LiteralCommand("tag @e remove %s", tag),
    ]


std_namespace = Namespace("mcutils_reborn_std")
STD_OBJECTIVE = UniqueScoreboardObjective("mcutils_reborn", std_namespace)

STD_ARG = std_namespace.get_unique_scoreboard_var("arg")
STD_RET = std_namespace.get_unique_scoreboard_var("ret")

STD_TAG = UniqueTag("mcutils_reborn", std_namespace)

STD_LOAD_TAG = std_namespace.create_function_tag("load")

with std_namespace.create_function("load", tags={"minecraft:load"}) as load:
    load.describe("Load the mcutils_reborn standard library.")
    load.add_command(
        *tools.log("mcutils_reborn", "Load standard library..."),

        Comment("create the std objective"),
        LiteralCommand("scoreboard objectives add %s dummy", STD_OBJECTIVE),

        Comment("reset the std objective"),
        LiteralCommand("scoreboard players reset * %s", STD_OBJECTIVE),

        Comment("Kill all entities with the std tag"),
        LiteralCommand("kill @e[tag=%s]", STD_TAG),

        FunctionCall(STD_LOAD_TAG),

        *tools.log("mcutils_reborn", "Finished reloading!"),
    )

from .object import *
from .stack import *
