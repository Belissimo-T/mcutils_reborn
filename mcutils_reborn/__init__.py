import typing


class Pathable:
    parent: typing.Optional["Namespace"] = None
    name: str

    def path(self) -> list[str]:
        if self.parent is None:
            return [self.name]

        return [*self.parent.path(), self.name]


class Namespace(Pathable):
    def __init__(self, name: str):
        self.name = name
        self.children: dict[str, Pathable] = {}

    def create_namespace(self, *args, **kwargs) -> "Namespace":
        namespace = Namespace(*args, **kwargs)
        self.add(namespace)

        return namespace

    def create_function(self, *args, **kwargs) -> "Function":
        function = Function(*args, **kwargs)
        self.add(function)

        return function

    def create_mcfunction(self, *args, **kwargs) -> "MCFunction":
        mcfunction = MCFunction(*args, **kwargs)
        self.add(mcfunction)

        return mcfunction

    def create_function_tag(self, name: str) -> "FunctionTag":
        function_tag = FunctionTag(name, self)
        function_tag.parent = self

        return function_tag

    def create_class(self, *args, **kwargs) -> "Class":
        cls = Class(*args, **kwargs)
        self.add(cls)

        return cls

    def create_template(self, *args, **kwargs) -> "Template":
        template = Template(*args, **kwargs)
        self.add(template)

        return template

    def get_unique_scoreboard_var(self, player: str, objective: "str | UniqueString | None" = None) -> "ScoreboardVar":
        if objective is None:
            from .lib.std import STD_OBJECTIVE
            objective = STD_OBJECTIVE

        return ScoreboardVar(UniqueScoreboardPlayer(player, self), objective)

    def get(self, name: str):
        return self.children[name]

    def get_all_mcfunctions(self) -> dict[tuple[str, ...], "MCFunction"]:
        mcfunctions = {}

        for child in self.children.values():
            if isinstance(child, MCFunction):
                mcfunctions[tuple(child.path())] = child

            elif isinstance(child, Namespace):
                if isinstance(child, Function):
                    assert child.was_ended, f"Function {path_to_str(child.path())} was not ended"

                mcfunctions |= child.get_all_mcfunctions()

        return mcfunctions

    def add(self, *namespaces: Pathable):
        for namespace in namespaces:
            self.children[namespace.name] = namespace
            namespace.parent = self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class FunctionTag(Pathable):
    def __init__(self, name: str, parent: Namespace):
        self.name = name
        self.parent = parent


class MCFunction(Pathable):
    """Represents a single mcfunction file."""

    def __init__(self, name: str, tags: set[str | FunctionTag] | None = None, description: str = ""):
        self.description = description
        self.name = name
        self.tags = set() if tags is None else tags
        self.commands: list[Command] = []
        self.continuation: MCFunction | None = None

    def add_command(self, command: "Command"):
        self.commands.append(command)


class Function(Namespace):
    """Represents a function. May contain multiple mcfunctions."""

    def __init__(self, name: str, args: tuple[str] = (), *, description: str = "", tags: set[str | FunctionTag] = None):
        super().__init__(name)

        tags = set() if tags is None else tags

        self.args = args

        self.continuation: MCFunction | None = None
        self.entry_point = self.create_mcfunction(self.name, tags=tags, description=description)
        self.current_mcfunction = self.entry_point

        self.was_ended = False

        self.init()

    def describe(self, description: str):
        self.entry_point.description = description

    def init(self):
        # pop arguments from stack into scoreboard vars
        # create local scope
        ...

    def add_command(self, *commands_: "Command"):
        assert not self.was_ended

        for command in commands_:
            self.current_mcfunction.add_command(command)

    def comment(self, *args, **kwargs):
        self.add_command(Comment(*args, **kwargs))

    def c_call_function(self,
                        function: "Function", *,
                        arg: "Expression | None" = None,
                        varargs: typing.Sequence["Expression"] = ()):
        self.comment(f"calling function %s"
                     f"{' with STD_ARG' * bool(arg)}"
                     f"{f' with {len(varargs)} varargs' * bool(varargs)}",
                     PathString(function))

        for i, vararg in enumerate(varargs):
            # self.comment(f"push vararg {i}:")
            self.c_call_function(std_stack_push(stack_nr=STD_ARGSTACK), arg=vararg)

        if arg is not None:
            # self.comment(f"set STD_ARG")
            self.add_command(
                var_to_var(arg, STD_ARG)
            )

        # self.comment(f"call function")
        self.add_command(FunctionCall(function.entry_point))

        # self.comment("done")

    def c_if(self, condition: "Condition") -> "Function":
        if_ = self.create_function(f"if{len(self.children)}")
        new_mcfunc = self.create_mcfunction(f"if-continue{len(self.children)}")

        string, u_strings = condition.to_str()
        self.add_command(
            ComposedCommand(
                LiteralCommand(f"execute if {string} run", *u_strings),
                FunctionCall(if_.entry_point)
            ),
            ComposedCommand(
                LiteralCommand(f"execute unless {string} run", *u_strings),
                FunctionCall(new_mcfunc)
            )
        )

        if_.continuation = self.current_mcfunction = new_mcfunc

        return if_

    def c_while(self):
        raise NotImplementedError

    def end(self):
        if self.was_ended:
            return

        self.current_mcfunction.continuation = self.continuation
        self.was_ended = True

    def return_(self, var: "Expression"):
        from .lib.std import STD_RET

        self.add_command(
            var_to_var(var, STD_RET)
        )

        self.current_mcfunction.continuation = None

    def __exit__(self, exc_type, exc_value, traceback):
        self.end()


class Template(Namespace):
    def __init__(self, name: str, template: typing.Callable[[...], Function]):
        super().__init__(name)

        self.template = template
        self.functions: dict[tuple[tuple[str, typing.Any], ...], Function] = {}

    def __call__(self, **kwargs):
        # noinspection PyTypeChecker
        converted_kwargs: tuple[tuple[str, typing.Any]] = tuple(kwargs.items())

        if converted_kwargs not in self.functions:
            func = self.template(**kwargs)
            func.end()
            self.functions[converted_kwargs] = func
            self.add(func)

        return self.functions[converted_kwargs]


class Class(Namespace):
    def __init__(self, name: str, inherits_from: typing.Iterable["Class"] = ()):
        super().__init__(name)

        self.inherits_from = inherits_from

    def get(self, name: str):
        try:
            return super().get(name)
        except KeyError:
            for parent in self.inherits_from:
                try:
                    return parent.get(name)
                except KeyError:
                    continue

            raise


from .commands import *
from .expressions import *
from .conversion import var_to_var, add_in_place
from .lib.std import *
from .exceptions import *
from .export import *
from .conditions import *
from . import tools
