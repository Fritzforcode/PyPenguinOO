from json        import loads
from abc         import ABC, abstractmethod
from typing      import Any
from dataclasses import dataclass, field

from pypenguin.utility import GreprClass, ThanksError, ValidationConfig, FirstToSecondConversionError, DeserializationError
from pypenguin.utility import AA_TYPE, AA_HEX_COLOR

from pypenguin.core.block_api import FICAPI
from pypenguin.core.custom_block import SRCustomBlockOpcode, SRCustomBlockOptype

@dataclass(repr=False)
class FRMutation(GreprClass, ABC):
    """
    The first representation for the mutation of a block. Mutations hold special information, which only special blocks have.
    """
    _grepr = True
    _grepr_fields = ["tag_name", "children"]
    
    tag_name: str # always "mutation"
    children: list # always []

    def __post_init__(self) -> None:
        """
        Ensure my assumptions about mutations were correct.
        
        Returns:
            None
        """
        if (self.tag_name != "mutation") or (self.children != []):
            raise ThanksError()

    @classmethod
    @abstractmethod
    def from_data(cls, data: dict[str, Any]) -> "FRMutation":
        """
        Create a mutation from raw data.
        
        Args:
            data: the raw data
        
        Returns:
            the mutation
        """

    @abstractmethod
    def step(self, block_api: FICAPI) -> "SRMutation":
        """
        Convert a mutation from first into second representation.
        
        Args:
            block_api: API used to fetch information about other blocks
        
        Returns:
            the second representation of the mutation
        """

@dataclass(repr=False)
class FRCustomBlockArgumentMutation(FRMutation):
    """
    The first representation for the mutation of a custom block's argument reporter
    """
    _grepr_fields = FRMutation._grepr_fields + ["color"]
    
    color: tuple[str, str, str]
    _argument_name: str | None = field(init=False)
    
    def __post_init__(self) -> None:
        """
        Create the empty '_argument_name' attribute.
        
        Returns:
            None
        """
        super().__post_init__()
        self._argument_name = None
    
    @classmethod
    def from_data(cls, data: dict[str, str]) -> "FRCustomBlockArgumentMutation":
        """
        Create a custom block argument mutation from raw data.
        
        Args:
            data: the raw data
        
        Returns:
            the mutation
        """
        return cls(
            tag_name = data["tagName" ],
            children = data["children"],
            color = tuple(loads(data["color"])),
        )
    
    def store_argument_name(self, name: str) -> None:
        """
        Temporarily store the argument name so it can be used later when the step method is called.
        I know doing it this way isn't very great; there should be no huge consequences though
        
        Args:
            name: the argument name
        
        Returns:
            None
        """
        self._argument_name = name
    
    def step(self, block_api: FICAPI) -> "SRCustomBlockArgumentMutation":
        """
        Convert a custom block argument mutation from first into second representation.
        
        Args:
            block_api: API used to fetch information about other blocks
        
        Returns:
            the second representation of the mutation
        """
        if getattr(self, "_argument_name", None) is None:
            raise FirstToSecondConversionError("Argument name must be set before SR conversion")
        return SRCustomBlockArgumentMutation(
            argument_name = self._argument_name,
            color1        = self.color[0],
            color2        = self.color[1],
            color3        = self.color[2],
        )

@dataclass(repr=False)
class FRCustomBlockMutation(FRMutation):
    """
    The first representation for the mutation of a custom block definition
    """
    _grepr_fields = FRMutation._grepr_fields + ["proccode", "argument_ids", "argument_names", "argument_defaults", "warp", "returns", "edited", "optype", "color"]
    
    proccode: str
    argument_ids: list[str]
    argument_names: list[str]
    argument_defaults: list[str]
    warp: bool
    returns: bool | None
    edited: bool # seems to always be true
    optype: str
    color: tuple[str, str, str]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "FRCustomBlockMutation":
        """
        Create a custom block definition mutation from raw data.
        
        Args:
            data: the raw data
        
        Returns:
            the mutation
        """
        if isinstance(data["warp"], bool):
            warp = data["warp"]
        elif isinstance(data["warp"], str):
            warp = loads(data["warp"])
        else: raise DeserializationError(f"Invalid value for warp: {data['warp']}")
        return cls(
            tag_name          = data["tagName" ],
            children          = data["children"],
            proccode          = data["proccode"],
            argument_ids      = loads(data["argumentids"     ]),
            argument_names    = loads(data["argumentnames"   ]),
            argument_defaults = loads(data["argumentdefaults"]),
            warp              = warp,
            returns           = loads(data["returns"]),
            edited            = loads(data["edited" ]),
            optype            = loads(data["optype" ]) if "optype" in data else "statement",
            color       = tuple(loads(data["color"  ])),
        )
    
    def step(self, block_api: FICAPI) -> "SRCustomBlockMutation":
        """
        Convert a custom block definition mutation from first into second representation.
        
        Args:
            block_api: API used to fetch information about other blocks
        
        Returns:
            the second representation of the mutation
        """
        return SRCustomBlockMutation(
            custom_opcode     = SRCustomBlockOpcode.from_proccode_argument_names(
                proccode          = self.proccode,
                argument_names    = self.argument_names,
            ),
            no_screen_refresh = self.warp,
            optype            = SRCustomBlockOptype.from_code(self.optype),
            color1            = self.color[0],
            color2            = self.color[1],
            color3            = self.color[2],
        )

@dataclass(repr=False)
class FRCustomBlockCallMutation(FRMutation):
    """
    The first representation for the mutation of a custom block call
    """
    _grepr_fields = FRMutation._grepr_fields + ["proccode", "argument_ids", "warp", "returns", "edited", "optype", "color"]
    
    proccode: str
    argument_ids: list[str]
    warp: bool
    returns: bool | None
    edited: bool # seems to always be true
    optype: str
    color: tuple[str, str, str]
    
    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "FRCustomBlockCallMutation":
        """
        Create a custom block call mutation from raw data.
        
        Args:
            data: the raw data
        
        Returns:
            the mutation
        """
        if isinstance(data["warp"], bool):
            warp = data["warp"]
        elif isinstance(data["warp"], str):
            warp = loads(data["warp"])
        else: raise DeserializationError(f"Invalid value for warp: {data['warp']}")
        return cls(
            tag_name     = data["tagName" ],
            children     = data["children"],
            proccode     = data["proccode"],
            argument_ids = loads(data["argumentids"]),
            warp         = warp,
            returns      = loads(data["returns"]),
            edited       = loads(data["edited" ]),
            optype       = loads(data["optype" ]) if "optype" in data else "statement",
            color  = tuple(loads(data["color"  ])),
        )
    
    def step(self, block_api: FICAPI) -> "SRCustomBlockCallMutation":
        """
        Convert a custom block call mutation from first into second representation.
        
        Args:
            block_api: API used to fetch information about other blocks
        
        Returns:
            the second representation of the mutation
        """
        complete_mutation = block_api.get_cb_mutation(self.proccode) # Get complete mutation
        return SRCustomBlockCallMutation(
            custom_opcode      = SRCustomBlockOpcode.from_proccode_argument_names(
                proccode          = self.proccode,
                argument_names    = complete_mutation.argument_names,
            ),
        )

@dataclass(repr=False)
class FRStopScriptMutation(FRMutation):
    """
    The first representation for the mutation of a stop script mutation.
    """
    _grepr_fields = FRMutation._grepr_fields + ["has_next"]
    
    has_next: bool
    
    @classmethod
    def from_data(cls, data: dict[str, bool]) -> "FRStopScriptMutation":
        """
        Create a mutation for the "stop [this script v]" block from raw data.
        
        Args:
            data: the raw data
        
        Returns:
            the mutation
        """
        return cls(
            tag_name = data["tagName" ],
            children = data["children"],
            has_next = loads(data["hasnext"]),
        )
    
    def step(self, block_api: FICAPI) -> "SRStopScriptMutation":
        """
        Convert a stop script mutation from first into second representation.
        
        Args:
            block_api: API used to fetch information about other blocks
        
        Returns:
            the second representation of the mutation
        """
        return SRStopScriptMutation(
            is_ending_statement = not(self.has_next),
        )


@dataclass(repr=False)
class SRMutation(GreprClass, ABC):
    """
    The second representation for the mutation of a block. Mutations hold special information, which only special blocks have. This representation is much more user friendly then the first representation.
    """
    _grepr = True
    _grepr_fields = []

    @abstractmethod
    def validate(self, path: list, config: ValidationConfig) -> None:
        """
        Ensure the mutation is valid, raise ValidationError if not.
        
        Args:
            path: the path from the project to itself. Used for better errors
            config: Configuration for Validation Behaviour
        
        Returns:
            None
        """

@dataclass(repr=False)
class SRCustomBlockArgumentMutation(SRMutation):
    """
    The second representation for the mutation of a custom block argument reporter
    """
    _grepr_fields = FRMutation._grepr_fields + ["argument_name", "color1", "color2", "color3"]
    
    argument_name: str
    # hex format
    # what each color does, is unknown (for now)
    color1: str
    color2: str
    color3: str

    def validate(self, path: list, config: ValidationConfig) -> None:
        """
        Ensure the custom block argument mutation is valid, raise ValidationError if not.
        
        Args:
            path: the path from the project to itself. Used for better errors
            config: Configuration for Validation Behaviour
        
        Returns:
            None
        """
        AA_TYPE(self, path, "argument_name", str)
        AA_HEX_COLOR(self, path, "color1")
        AA_HEX_COLOR(self, path, "color2")
        AA_HEX_COLOR(self, path, "color3")
    
@dataclass(repr=False)
class SRCustomBlockMutation(SRMutation):
    """
    The second representation for the mutation of a custom block definition
    """
    _grepr_fields = SRMutation._grepr_fields + ["custom_opcode", "no_screen_refresh", "optype", "color1", "color2", "color3"]
    
    custom_opcode: "SRCustomBlockOpcode"
    no_screen_refresh: bool
    optype: SRCustomBlockOptype
    
    # hex format
    # what each color does, is unknown (for now)
    color1: str
    color2: str
    color3: str
    
    def validate(self, path: list, config: ValidationConfig) -> None:
        """
        Ensure the custom block definition mutation is valid, raise ValidationError if not.
        
        Args:
            path: the path from the project to itself. Used for better errors
            config: Configuration for Validation Behaviour
        
        Returns:
            None
        """
        AA_TYPE(self, path, "custom_opcode", SRCustomBlockOpcode)
        AA_TYPE(self, path, "no_screen_refresh", bool)
        AA_TYPE(self, path, "optype", SRCustomBlockOptype)
        AA_HEX_COLOR(self, path, "color1")
        AA_HEX_COLOR(self, path, "color2")
        AA_HEX_COLOR(self, path, "color3")

        self.custom_opcode.validate(path+["custom_opcode"], config)

@dataclass(repr=False)    
class SRCustomBlockCallMutation(SRMutation):
    """
    The second representation for the mutation of a custom block call
    """
    _grepr_fields = SRMutation._grepr_fields + ["custom_opcode"]
    
    custom_opcode: "SRCustomBlockOpcode"
    
    def validate(self, path: list, config: ValidationConfig) -> None:
        """
        Ensure the custom block call mutation is valid, raise ValidationError if not.
        
        Args:
            path: the path from the project to itself. Used for better errors
            config: Configuration for Validation Behaviour
        
        Returns:
            None
        """
        AA_TYPE(self, path, "custom_opcode", SRCustomBlockOpcode)

        self.custom_opcode.validate(path+["custom_opcode"], config)

@dataclass(repr=False)
class SRStopScriptMutation(SRMutation):
    """
    The second representation for the mutation of a "stop [this script v] block
    """
    _grepr_fields = SRMutation._grepr_fields + ["is_ending_statement"]
    
    is_ending_statement: bool

    def validate(self, path: list, config: ValidationConfig) -> None:
        """
        Ensure the stop script mutation is valid, raise ValidationError if not.
        
        Args:
            path: the path from the project to itself. Used for better errors
            config: Configuration for Validation Behaviour
        
        Returns:
            None
        """
        AA_TYPE(self, path, "is_ending_statement", bool)

