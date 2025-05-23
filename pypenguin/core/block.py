from typing      import Any, TYPE_CHECKING
from dataclasses import field
from abc         import ABC, abstractmethod

from pypenguin.utility           import (
    grepr_dataclass, ValidationConfig, get_closest_matches, tuplify,
    AA_TYPE, AA_NONE, AA_NONE_OR_TYPE, AA_COORD_PAIR, AA_LIST_OF_TYPE, AA_DICT_OF_TYPE, AA_MIN_LEN,
    DeserializationError, FirstToInterConversionError, InterToSecondConversionError,
    UnnecessaryInputError, MissingInputError, UnnecessaryDropdownError, MissingDropdownError, InvalidOpcodeError, InvalidBlockShapeError,
)
from pypenguin.opcode_info       import OpcodeInfoAPI, OpcodeInfo, InputType, InputMode, OpcodeType, SpecialCaseType
from pypenguin.important_opcodes import *

from pypenguin.core.block_mutation import FRMutation, SRMutation
from pypenguin.core.comment        import SRComment
from pypenguin.core.context        import CompleteContext
from pypenguin.core.dropdown       import SRDropdownValue

if TYPE_CHECKING:
    from pypenguin.core.block_api      import FIConversionAPI, ValidationAPI

@grepr_dataclass(grepr_fields=["opcode", "next", "parent", "inputs", "fields", "shadow", "top_level", "x", "y", "comment", "mutation"])
class FRBlock:
    """
    The first representation for a block. It is very close to the raw data in a project
    """

    opcode: str
    next: str | None
    parent: str | None
    inputs: dict[str, (
       tuple[int, str | tuple] 
     | tuple[int, str | tuple, str | tuple]
    )]
    fields: dict[str, tuple[str, str] | tuple[str, str, str]]
    shadow: bool
    top_level: bool
    x: int | float | None = None
    y: int | float | None = None
    comment: str | None = None # a comment id
    mutation: "FRMutation | None" = None

    @classmethod
    def from_data(cls, data: dict[str, Any], info_api: OpcodeInfoAPI) -> "FRBlock":
        """
        Deserializes raw data into a FRBlock
        
        Args:
            data: the raw data
            info_api: the opcode info api used to fetch information about opcodes
        
        Returns:
            the FRBlock
        """
        opcode = data["opcode"]
        opcode_info = info_api.get_info_by_old(opcode)
        if opcode_info.old_mutation_cls is None:
            if "mutation" in data:
                raise DeserializationError(f"Invalid mutation for FRBlock with opcode {repr(opcode)}: {data['mutation']}")
            mutation = None
        else:
            if "mutation" not in data:
                cls_name = opcode_info.old_mutation_cls.__name__
                raise DeserializationError(f"Missing mutation of type {cls_name} for FRBlock with opcode {repr(opcode)}")
            mutation = opcode_info.old_mutation_cls.from_data(data["mutation"])
        return cls(
            opcode    = opcode,
            next      = data["next"    ],
            parent    = data["parent"  ],
            inputs    = tuplify(data["inputs"]),
            fields    = tuplify(data["fields"]),
            shadow    = data["shadow"  ],
            top_level = data["topLevel"],
            x         = data.get("x", None),
            y         = data.get("y", None),
            comment   = data.get("comment", None),
            mutation  = mutation,
        )
    
    @classmethod
    def from_tuple(cls, 
            data: tuple[str, str, str] | tuple[str, str, str, int|float, int|float],
            parent_id: str | None,
        ) -> "FRBlock":
        """
        Deserializes a tuple into a FRBlock
        
        Args:
            data: the raw data
        
        Returns:
            the FRBlock
        """
        if   len(data) == 3:
            if parent_id is None:
                raise DeserializationError(f"Invalid parent_id for FRBlock conversion of {data}: {parent_id}")
            x = None
            y = None
        elif len(data) == 5: 
            if parent_id is not None:
                raise DeserializationError(f"Invalid parent_id for FRBlock conversion of {data}: {parent_id}")
            x = data[3]
            y = data[4]
        else: raise DeserializationError(f"Invalid data for FRBlock conversion: {data}")
        
        if data[0] == OPCODE_VAR_VALUE_NUM:
            return FRBlock(
                opcode    = OPCODE_VAR_VALUE,
                next      = None,
                parent    = parent_id,
                inputs    = {},
                fields    = {"VARIABLE": (data[1], data[2], "")},
                shadow    = False,
                top_level = x is not None,
                x         = x,
                y         = y,
                comment   = None,
                mutation  = None,
            )
        elif data[0] == OPCODE_LIST_VALUE_NUM:
           return FRBlock(
                opcode    = OPCODE_LIST_VALUE,
                next      = None,
                parent    = parent_id,
                inputs    = {},
                fields    = {"LIST": (data[1], data[2], "")},
                shadow    = False,
                top_level = x is not None,
                x         = x,
                y         = y,
                comment   = None,
                mutation  = None,
            )
        else: raise DeserializationError(f"Invalid constant(first element) for FRBlock conversion: {data[0]}")

    def step(self, 
        ficapi: "FIConversionAPI", 
        info_api: OpcodeInfoAPI, 
        own_id: str
    ) -> "IRBlock":
        """
        Converts a FRBlock into a IRBlock
        
        Args:
            ficapi: API used to fetch information about other blocks
            info_api: the opcode info api used to fetch information about opcodes
        
        Returns:
            the IRBlock
        """
        opcode_info = info_api.get_info_by_old(self.opcode)
        pre_handler = opcode_info.get_special_case(SpecialCaseType.PRE_FR_STEP)
        if pre_handler is not None:
            self = pre_handler.call(ficapi=ficapi, block=self)
        
        instead_handler = opcode_info.get_special_case(SpecialCaseType.FR_STEP)
        if instead_handler is None:
            new_inputs = self._step_inputs(
                ficapi  = ficapi,
                info_api   = info_api,
                opcode_info = opcode_info,
                own_id     = own_id,
            )
            new_dropdowns = {}
            for dropdown_id, dropdown_value in self.fields.items():
                new_dropdowns[dropdown_id] = dropdown_value[0]
            
            new_block = IRBlock(
                opcode       = self.opcode,
                inputs       = new_inputs,
                dropdowns    = new_dropdowns,
                position     = (self.x, self.y) if self.top_level else None,
                comment      = None if self.comment  is None else ficapi.get_comment(self.comment),
                mutation     = None if self.mutation is None else self.mutation.step(
                    ficapi = ficapi,
                ),
                next         = None if self.next     is None else IRBlockReference(self.next),
                is_top_level = self.top_level,
            )
        else:
            new_block = instead_handler.call(ficapi=ficapi, block=self)
        return new_block

    def _step_inputs(self, 
        ficapi: "FIConversionAPI", 
        info_api: OpcodeInfoAPI,
        opcode_info: OpcodeInfo,
        own_id: str
    ) -> dict[str, "IRInputValue"]:
        """
        *[Internal Method]* Converts the inputs of a FRBlock into the IR Fromat
        
        Args:
            ficapi: API used to fetch information about other blocks
            info_api: the opcode info api used to fetch information about opcodes
            opcode_info: the Information about the block's opcode
        
        Returns:
            the inputs in IR Format
        """
        input_modes = opcode_info.get_old_input_ids_modes(block=self, ficapi=ficapi)
        
        new_inputs = {}
        for input_id, input_value in self.inputs.items():
            input_mode = input_modes[input_id]

            references      = []
            immediate_block = None
            text            = None
            for item in input_value[1:]: # ignore first item(some irrelevant number)
                if isinstance(item, str):
                    references.append(IRBlockReference(item))
                elif isinstance(item, tuple) and item[0] in {4, 5, 6, 7, 8, 9, 10, 11}:
                    text = item[1]
                elif isinstance(item, tuple) and item[0] in {12, 13}:
                    immediate_fr_block = FRBlock.from_tuple(item, parent_id=own_id)
                    immediate_block = immediate_fr_block.step(
                        ficapi = ficapi,
                        info_api  = info_api,
                        own_id    = None, # None is fine, because tuple blocks can't possibly contain more tuple blocks 
                    )
                else: raise FirstToInterConversionError(f"Invalid input value {input_value} for input {repr(input_id)}")

            new_inputs[input_id] = IRInputValue(
                mode            = input_mode,
                references      = references,
                immediate_block = immediate_block,
                text            = text,
            )
        
        # Check for missing inputs and give a default value where possible otherwise raise
        for input_id, input_mode in input_modes.items():
            if input_id in new_inputs:
                continue
            if input_mode.can_be_missing():
                new_inputs[input_id] = IRInputValue(
                    mode            = input_mode,
                    references      = [],
                    immediate_block = None,
                    text            = None,
                )
            else: raise FirstToInterConversionError(f"Didn't expect input {repr(input_id)} missing")
        
        return new_inputs



@grepr_dataclass(grepr_fields=["opcode", "inputs", "dropdowns", "comment", "mutation", "position", "next", "is_top_level"])
class IRBlock:
    """
    The intermediate representation for a block. It has similarities with SRBlock but uses an id system
    """
    
    opcode: str
    inputs: dict[str, "IRInputValue"]
    dropdowns: dict[str, Any]
    comment: SRComment | None
    mutation: "SRMutation | None"
    position: tuple[int | float, int | float] | None
    next: "IRBlockReference | None"
    is_top_level: bool

    def step(self, 
        all_blocks: dict[str, "IRBlock"],
        info_api: OpcodeInfoAPI,
    ) -> tuple[tuple[int|float,int|float] | None, list["SRBlock | str"]]:
        """
        Converts a IRBlock into a SRBlock
        
        Args:
            all_blocks: a dictionary of all blocks
            info_api: the opcode info api used to fetch information about opcodes
        
        Returns:
            the SRBlock
        """
        opcode_info = info_api.get_info_by_old(self.opcode)
        if opcode_info.opcode_type == OpcodeType.MENU: # The attribute is fine because DYNAMIC should never generate MENU
            return (None, [list(self.dropdowns.values())[0]])
            """ example:
            {
                opcode="#TOUCHING OBJECT MENU",
                options={"TOUCHINGOBJECTMENU": ["object", "_mouse_"]},
                ...
            }
            --> "_mouse_" """
        
        old_new_input_ids = opcode_info.get_old_new_input_ids(block=self, ficapi=None)
        # maps old input ids to new input ids # ficapi isn't necessary for a IRBlock 
        
        new_inputs = {}
        for input_id, input_value in self.inputs.items():
            sub_scripts: list[list[SRBlock|str]] = []
            if input_value.immediate_block is not None:
                _, sub_blocks = input_value.immediate_block.step(
                    all_blocks = all_blocks,
                    info_api   = info_api,
                )
                sub_scripts.append(sub_blocks)
            
            for sub_reference in input_value.references: 
                sub_block = all_blocks[sub_reference]
                _, sub_blocks = sub_block.step(
                    all_blocks    = all_blocks,
                    info_api      = info_api,
                )
                sub_scripts.append(sub_blocks)
            
            script_count = len(sub_scripts)
            if script_count == 2:
                sub_script  = sub_scripts[0] # blocks of first script
                sub_block_a = sub_scripts[0][0] # first block of first script
                sub_block_b = sub_scripts[1][0] # first block of second script
            elif script_count == 1:
                sub_script  = sub_scripts[0] # blocks of first script
                sub_block_a = sub_scripts[0][0] # first block of frist script
                sub_block_b = None
            elif script_count == 0:
                sub_script  = []
                sub_block_a = None
                sub_block_b = None
            else: raise InterToSecondConversionError(f"Invalid script count {script_count}")
            
            input_blocks   = []
            input_block    = None
            input_text     = None
            input_dropdown = None
            
            match input_value.mode:
                case InputMode.BLOCK_AND_TEXT:
                    assert script_count in {0, 1}
                    input_block = sub_block_a
                    input_text  = input_value.text
                case InputMode.BLOCK_AND_BROADCAST_DROPDOWN:
                    assert script_count in {0, 1}
                    input_block     = sub_block_a
                    input_dropdown  = input_value.text
                case InputMode.BLOCK_ONLY:
                    assert script_count in {0, 1}
                    input_block = sub_block_a
                case InputMode.SCRIPT:
                    assert script_count in {0, 1}
                    input_blocks = sub_script
                case InputMode.BLOCK_AND_DROPDOWN:
                    assert script_count in {1, 2}
                    if   script_count == 1:
                        input_block    = None
                        input_dropdown = sub_block_a
                    elif script_count == 2:
                        input_block    = sub_block_a
                        input_dropdown = sub_block_b
                case InputMode.BLOCK_AND_MENU_TEXT:
                    assert script_count in {1, 2}
                    if   script_count == 1:
                        input_block  = None
                        input_text   = sub_block_a
                    elif script_count == 2:
                        input_block  = sub_block_a
                        input_text   = sub_block_b

            if input_dropdown is not None:
                input_type = opcode_info.get_input_info_by_old(input_id).type
                dropdown_type = input_type.get_corresponding_dropdown_type()
                input_dropdown = SRDropdownValue.from_tuple(dropdown_type.translate_old_to_new_value(input_dropdown))

            new_input_id = old_new_input_ids[input_id]
            new_inputs[new_input_id] = SRInputValue.from_mode(
                mode     = input_value.mode,
                blocks   = input_blocks,
                block    = input_block,
                text     = input_text,
                dropdown = input_dropdown,
            )
        
        input_types = opcode_info.get_new_input_ids_types(block=self, ficapi=None) 
        # maps input ids to their types # ficapi isn't necessary for a IRBlock
        for new_input_id in input_types.keys():
            if new_input_id not in new_inputs:
                input_mode = input_types[new_input_id].get_mode()
                if input_mode.can_be_missing():
                    new_inputs[new_input_id] = SRInputValue.from_mode(mode=input_mode)
                else:
                    raise InterToSecondConversionError(f"For a block with opcode {repr(self.opcode)}, input {repr(new_input_id)} is missing")
        
        new_dropdowns = {}
        for dropdown_id, dropdown_value in self.dropdowns.items():
            dropdown_type = opcode_info.get_dropdown_info_by_old(dropdown_id).type
            new_dropdown_id = opcode_info.get_new_dropdown_id(dropdown_id)
            new_dropdowns[new_dropdown_id] = SRDropdownValue.from_tuple(dropdown_type.translate_old_to_new_value(dropdown_value))

        new_block = SRBlock(
            opcode    = info_api.get_new_by_old(self.opcode),
            inputs    = new_inputs,
            dropdowns = new_dropdowns,
            comment   = self.comment,
            mutation  = self.mutation,
        )
        new_blocks = [new_block]
        if self.next is not None:
            next_block = all_blocks[self.next]
            _, next_blocks = next_block.step(
                all_blocks    = all_blocks,
                info_api      = info_api,
            )
            new_blocks.extend(next_blocks)
        
        return (self.position, new_blocks) 
 
@grepr_dataclass(grepr_fields=["mode", "references", "immediate_block", "text"])
class IRInputValue:
    """
    The intermediate representation for the value of a block's input
    """
    
    mode: InputMode
    references: list["IRBlockReference"]
    immediate_block: IRBlock | None
    text: str | None

@grepr_dataclass(grepr_fields=["id"], frozen=True, unsafe_hash=True)
class IRBlockReference:
    """
    A block reference in intermediate representation. Basis for the temporary id system
    """
    
    id: str



@grepr_dataclass(grepr_fields=["position", "blocks"])
class SRScript:
    """
    The second representation for a script. 
    It uses a nested block structure and is much more user friendly then the first representation
    """

    position: tuple[int | float, int | float]
    blocks: list["SRBlock"]

    def validate(self, 
        path: list, 
        config: ValidationConfig,
        info_api: OpcodeInfoAPI,
        validation_api: "ValidationAPI",
        context: CompleteContext,
    ) -> None:
        """
        Ensure a SRScript is valid, raise ValidationError if not
        
        Args:
            path: the path from the project to itself. Used for better error messages
            config: Configuration for Validation Behaviour
            info_api: the opcode info api used to fetch information about opcodes
            validation_api: API used to fetch information about other blocks 
            context: Context about parts of the project. Used to validate the values of dropdowns
        
        Returns:
            None
        
        Raises:
            ValidationError: if the SRScript is invalid
        """
        AA_COORD_PAIR(self, path, "position")
        AA_LIST_OF_TYPE(self, path, "blocks", SRBlock)
        AA_MIN_LEN(self, path, "blocks", min_len=1)
        
        for i, block in enumerate(self.blocks):
            current_path = path+["blocks", i]
            block.validate(
                path             = current_path,
                config           = config,
                info_api         = info_api,
                validation_api   = validation_api,
                context          = context,
                expects_reporter = False,
            )
            opcode_info = info_api.get_info_by_new(block.opcode)
            opcode_type = opcode_info.get_opcode_type(block=block, validation_api=validation_api)
            SRBlock.validate_opcode_type(
                opcode_type  = opcode_type,
                path         = current_path,
                config       = config,
                is_top_level = True,
                is_first     = (i == 0),
                is_last      = ((i+1) == len(self.blocks)),
            )

@grepr_dataclass(grepr_fields=["opcode", "inputs", "dropdowns", "comment", "mutation"])
class SRBlock:
    """
    The second representation for a block. 
    It uses a nested block structure and is much more user friendly then the first representation
    """
    
    opcode: str
    inputs: dict[str, "SRInputValue"]
    dropdowns: dict[str, SRDropdownValue]
    comment: SRComment | None
    mutation: "SRMutation | None"
    
    def validate(self, 
        path: list, 
        config: ValidationConfig,
        info_api: OpcodeInfoAPI,
        validation_api: "ValidationAPI", 
        context: CompleteContext,
        expects_reporter: bool,
    ) -> None:
        """
        Ensure a SRBlock is valid, raise ValidationError if not
        
        Args:
            path: the path from the project to itself. Used for better error messages
            config: Configuration for Validation Behaviour
            info_api: the opcode info api used to fetch information about opcodes
            validation_api: API used to fetch information about other blocks 
            context: Context about parts of the project. Used to validate dropdowns
            expects_reporter: Wether this block should be a reporter
        
        Returns:
            None
        
        Raises:
            ValidationError: if the SRBlock is invalid
            InvalidOpcodeError(ValidationError): if the opcode is not a defined opcode
            UnnecessaryInputError(ValidationError): if a key of inputs is not expected for the specific opcode
            MissingInputError(ValidationError): if an expected key of inputs for the specific opcode is missing
            UnnecessaryDropdownError(ValidationError): if a key of dropdowns is not expected for the specific opcode
            MissingDropdownError(ValidationError): if an expected key of dropdowns for the specific opcode is missing
            InvalidBlockShapeError(ValidationError): if a reporter block was expected but a non-reporter block was found
        """
        AA_TYPE(self, path, "opcode", str)
        AA_DICT_OF_TYPE(self, path, "inputs"   , key_t=str, value_t=SRInputValue   )
        AA_DICT_OF_TYPE(self, path, "dropdowns", key_t=str, value_t=SRDropdownValue)
        AA_NONE_OR_TYPE(self, path, "comment", SRComment)
        AA_NONE_OR_TYPE(self, path, "mutation", SRMutation)
        
        cls_name = self.__class__.__name__
        opcode_info = info_api.get_info_by_new_safe(self.opcode)
        if opcode_info is None:
            closest_matches = get_closest_matches(self.opcode, info_api.get_all_new(), n=10)
            msg = (
                f"opcode of {cls_name} must be a defined opcode not {repr(self.opcode)}. "
                f"The closest matches are: \n  - "+"\n  - ".join([repr(m) for m in closest_matches])
            )
            raise InvalidOpcodeError(path, msg)
        
        if self.comment is not None:
            self.comment.validate(path+["comment"], config)
        
        if opcode_info.new_mutation_cls is None:
            AA_NONE(self, path, "mutation", condition="For this opcode")
        else:
            AA_TYPE(self, path, "mutation", opcode_info.new_mutation_cls, condition="For this opcode")
            self.mutation.validate(path+["mutation"], config)

        input_types = opcode_info.get_new_input_ids_types(block=self, ficapi=None) 
        # maps input ids to their types # ficapi isn't necessary for a IRBlock
        
        for new_input_id, input in self.inputs.items():
            if new_input_id not in input_types.keys():
                raise UnnecessaryInputError(path, 
                    f"inputs of {cls_name} with opcode {repr(self.opcode)} includes unnecessary input {repr(new_input_id)}",
                )
            input.validate(
                path           = path+["inputs", (new_input_id,)],
                config         = config,
                info_api       = info_api,
                validation_api = validation_api,
                context        = context,
                input_type     = input_types[new_input_id],
            )
        for new_input_id in input_types.keys():
            if new_input_id not in self.inputs:
                raise MissingInputError(path, 
                    f"inputs of {cls_name} with opcode {repr(self.opcode)} is missing input {repr(new_input_id)}",
                )
        
        new_dropdown_ids = opcode_info.get_all_new_dropdown_ids()
        for new_dropdown_id, dropdown in self.dropdowns.items():
            if new_dropdown_id not in new_dropdown_ids:
                raise UnnecessaryDropdownError(path, 
                    f"dropdowns of {cls_name} with opcode {repr(self.opcode)} includes unnecessary dropdown {repr(new_dropdown_id)}",
                )
            current_path = path+["dropdowns", (new_dropdown_id,)]
            dropdown.validate(current_path, config)
            dropdown.validate_value(
                path          = current_path,
                config        = config,
                dropdown_type = opcode_info.get_dropdown_info_by_new(new_dropdown_id).type,
                context       = context,
            )
        for new_dropdown_id in new_dropdown_ids:
            if new_dropdown_id not in self.dropdowns:
                raise MissingDropdownError(path, 
                    f"dropdowns of {cls_name} with opcode {repr(self.opcode)} is missing dropdown {repr(new_dropdown_id)}",
                )
        
        opcode_type = opcode_info.get_opcode_type(block=self, validation_api=validation_api)
        if expects_reporter and not(opcode_type.is_reporter()):
            raise InvalidBlockShapeError(path, "Expected a reporter block here")

        post_case = opcode_info.get_special_case(SpecialCaseType.POST_VALIDATION)
        if post_case is not None:
            post_case.call(path=path, block=self)

    @staticmethod
    def validate_opcode_type(
        path: list,
        config: ValidationConfig, 
        opcode_type: OpcodeType,
        is_top_level: bool,
        is_first: bool,
        is_last: bool,
    ) -> None:
        """
        Ensure a block shape is allowed at a specific location.  
        
        Args:
            path: the path from the project to itself. Used for better error messages
            config: Configuration for Validation Behaviour
            opcode_type: the opcode type of this block
            is_top_level: Wether this block is in a script(True) or in a substack(False)
            is_fist: Wether this block is the first in it's script/substack
            is_last: Wether this block is the last in it's script/substack
        
        Returns:
            None
        
        Raises:
            InvalidBlockShapeError(ValidationError): if the opcode_type of the block's opcode is invalid in a specific situation
        """
        if   opcode_type == OpcodeType.STATEMENT: pass
        elif opcode_type == OpcodeType.ENDING_STATEMENT:
            if not is_last: # when there is a next block
                raise InvalidBlockShapeError(path, "A block of type ENDING_STATEMENT must be the last block in it's script or substack")
        elif opcode_type == OpcodeType.HAT:
            if not is_top_level:
                raise InvalidBlockShapeError(path, "A block of type HAT is not allowed within a substack")
            elif not is_first:
                raise InvalidBlockShapeError(path, "A block of type HAT must to be the first block in it's script or substack")
        elif opcode_type.is_reporter():
            if not is_top_level:
                raise InvalidBlockShapeError(path, "A block of type ...REPORTER is not allowed within a substack")
            elif not(is_first and is_last):
                raise InvalidBlockShapeError(path, "If contained in a substack, a block of type ...REPORTER must be the only block in that substack")


@grepr_dataclass(grepr_fields=[], eq=False, init=False)
class SRInputValue(ABC):
    """
    The second representation for a block input. 
    It can contain a substack of blocks, a block, a text field and a dropdown
    **Please use the subclasses instead**
    **Be careful when accessing fields**, because only the subclasses guarantee there existance
    """
    
    # these aren't guaranteed to exist and are only listed for good typing
    blocks: list[SRBlock]     | None = field(init=False) 
    block: SRBlock            | None = field(init=False)
    text: str                 | None = field(init=False)
    dropdown: SRDropdownValue | None = field(init=False)

    def __init__(self) -> None:
        """
        Create a SRInputValue. 
        **Please use the subclasses or the from_mode method for concrete data. This method will raise a NotImplementedError.**

        Returns:
            None

        Raises:
            NotImplementedError: always
        """
        raise NotImplementedError("Please use the subclasses or the from_mode method for concrete data")

    def __eq__(self, other) -> bool:
        """
        Return self == other

        Args:
            other: value to compare to
        
        Returns:
            self == other
        """
        if not isinstance(other, SRInputValue):
            return NotImplemented
        if type(self) != type(other):
            return NotImplemented
        if len(self._grepr_fields) != len(other._grepr_fields):
            return False
        for attr in self._grepr_fields:
            if attr not in other._grepr_fields:
                return False
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True

    @classmethod
    def from_mode(cls,
        mode: InputMode,
        blocks: list[SRBlock]     | None = None,
        block: SRBlock            | None = None,
        text: str                 | None = None,
        dropdown: SRDropdownValue | None = None,
    ) -> "SRInputValue":
        """
        Creates a SRInputValue, given its mode and data
        
        Args:
            mode: the input mode
            blocks: the substack blocks
            block: the block of the input
            text: the text field of the input
            dropdown: the dropdown of the input
        
        Returns:
            the input value
        """
        match mode:
            case InputMode.BLOCK_AND_TEXT | InputMode.BLOCK_AND_MENU_TEXT:
                return SRBlockAndTextInputValue(block=block, text=text)
            case InputMode.BLOCK_AND_DROPDOWN | InputMode.BLOCK_AND_BROADCAST_DROPDOWN:
                return SRBlockAndDropdownInputValue(block=block, dropdown=dropdown)
            case InputMode.BLOCK_ONLY:
                return SRBlockOnlyInputValue(block=block)
            case InputMode.SCRIPT:
                return SRScriptInputValue(blocks=[] if blocks is None else blocks)

    @abstractmethod
    def validate(self, 
        path: list, 
        config: ValidationConfig,
        info_api: OpcodeInfoAPI,
        validation_api: "ValidationAPI", 
        context: CompleteContext, 
        input_type: InputType, 
    ) -> None:
        """
        Ensures this input is valid, raise ValidationError if not
        
        Args:
            path: the path from the project to itself. Used for better error messages
            config: Configuration for Validation Behaviour
            info_api: the opcode info api used to fetch information about opcodes
            validation_api: API used to fetch information about other blocks 
            context: Context about parts of the project. Used to validate dropdowns
            input_type: the type of this input. Used to valdiate dropdowns
        
        Returns:
            None
        
        Raises:
            ValidationError: if the SRInputValue is invalid
        """

    def _validate_block(self, 
        path: list, 
        config: ValidationConfig,
        info_api: OpcodeInfoAPI,
        validation_api: "ValidationAPI", 
        context: CompleteContext, 
    ) -> None:
        """
        *[Internal Method]* Ensures the block of this input is valid, raise ValidationError if not
        
        Args:
            path: the path from the project to itself. Used for better error messages
            config: Configuration for Validation Behaviour
            info_api: the opcode info api used to fetch information about opcodes
            validation_api: API used to fetch information about other blocks 
            context: Context about parts of the project. Used to validate dropdowns
        
        Returns:
            None
        
        Raises:
            ValidationError: if the block of the SRInputValue is invalid
        """
        block: SRBlock = self.block
        AA_NONE_OR_TYPE(self, path, "block", SRBlock)
        if block is not None:
            block.validate(
                path             = path+["block"],
                config           = config,
                info_api         = info_api,
                validation_api   = validation_api,
                context          = context,
                expects_reporter = True,
            )

@grepr_dataclass(grepr_fields=["block", "text"], parent_cls=SRInputValue, eq=False)
class SRBlockAndTextInputValue(SRInputValue):
    """
    The second representation for a block input, which has a text field and might contain a block
    """

    block: SRBlock | None
    text : str
    
    def validate(self, 
        path: list, 
        config: ValidationConfig,
        info_api: OpcodeInfoAPI,
        validation_api: "ValidationAPI", 
        context: CompleteContext, 
        input_type: InputType, 
    ) -> None:
        """
        Ensures this input is valid, raise ValidationError if not
        
        Args:
            path: the path from the project to itself. Used for better error messages
            config: Configuration for Validation Behaviour
            info_api: the opcode info api used to fetch information about opcodes
            validation_api: API used to fetch information about other blocks 
            context: Context about parts of the project. Used to validate dropdowns
            input_type: the type of this input. Used to valdiate dropdowns
        
        Returns:
            None
        
        Raises:
            ValidationError: if the SRBlockAndTextInputValue is invalid
        """
        self._validate_block(
            path           = path,
            config         = config,
            info_api       = info_api,
            validation_api = validation_api,
            context        = context,
        )
        AA_TYPE(self, path, "text", str)

@grepr_dataclass(grepr_fields=["block", "dropdown"], parent_cls=SRInputValue, eq=False)
class SRBlockAndDropdownInputValue(SRInputValue):
    """
    The second representation for a block input, which has a dropdown and might contain a block
    """
    
    block   : SRBlock         | None
    dropdown: SRDropdownValue | None

    def validate(self, 
        path: list, 
        config: ValidationConfig,
        info_api: OpcodeInfoAPI,
        validation_api: "ValidationAPI", 
        context: CompleteContext, 
        input_type: InputType, 
    ) -> None:
        """
        Ensures this input is valid, raise ValidationError if not
        
        Args:
            path: the path from the project to itself. Used for better error messages
            config: Configuration for Validation Behaviour
            info_api: the opcode info api used to fetch information about opcodes
            validation_api: API used to fetch information about other blocks 
            context: Context about parts of the project. Used to validate dropdowns
            input_type: the type of this input. Used to valdiate dropdowns
        
        Returns:
            None
        
        Raises:
            ValidationError: if the SRBlockAndDropdownInputValue is invalid
        """
        self._validate_block(
            path           = path,
            config         = config,
            info_api       = info_api,
            validation_api = validation_api,
            context        = context,
        )
        AA_NONE_OR_TYPE(self, path, "dropdown", SRDropdownValue)
        if self.dropdown is not None:
            current_path = path+["dropdown"]
            self.dropdown.validate(current_path, config)
            self.dropdown.validate_value(
                path          = current_path,
                config        = config,
                dropdown_type = input_type.get_corresponding_dropdown_type(),
                context       = context,
            )

@grepr_dataclass(grepr_fields=["block"], parent_cls=SRInputValue, eq=False)
class SRBlockOnlyInputValue(SRInputValue):
    """
    The second representation for a block input, which might contain a block
    """
    
    block: SRBlock | None

    def validate(self, 
        path: list, 
        config: ValidationConfig,
        info_api: OpcodeInfoAPI,
        validation_api: "ValidationAPI", 
        context: CompleteContext, 
        input_type: InputType, 
    ) -> None:
        """
        Ensures this input is valid, raise ValidationError if not
        
        Args:
            path: the path from the project to itself. Used for better error messages
            config: Configuration for Validation Behaviour
            info_api: the opcode info api used to fetch information about opcodes
            validation_api: API used to fetch information about other blocks 
            context: Context about parts of the project. Used to validate dropdowns
            input_type: the type of this input. Used to valdiate dropdowns
        
        Returns:
            None
        
        Raises:
            ValidationError: if the SRBlockOnlyInputValue is invalid
        """
        self._validate_block(
            path           = path,
            config         = config,
            info_api       = info_api,
            validation_api = validation_api,
            context        = context,
        )

@grepr_dataclass(grepr_fields=["blocks"], parent_cls=SRInputValue, eq=False)
class SRScriptInputValue(SRInputValue):
    """
    The second representation for a block input, which contains a substack of blocks
    """
    
    blocks: list[SRBlock]

    def validate(self, 
        path: list, 
        config: ValidationConfig,
        info_api: OpcodeInfoAPI,
        validation_api: "ValidationAPI", 
        context: CompleteContext, 
        input_type: InputType, 
    ) -> None:
        """
        Ensures this input is valid, raise ValidationError if not
        
        Args:
            path: the path from the project to itself. Used for better error messages
            config: Configuration for Validation Behaviour
            info_api: the opcode info api used to fetch information about opcodes
            validation_api: API used to fetch information about other blocks 
            context: Context about parts of the project. Used to validate dropdowns
            input_type: the type of this input. Used to valdiate dropdowns
        
        Returns:
            None
        
        Raises:
            ValidationError: if the SRScriptInputValue is invalid
        """
        AA_LIST_OF_TYPE(self, path, "blocks", SRBlock)
        for i, block in enumerate(self.blocks):
            current_path = path+["blocks", i]
            block.validate(
                path             = current_path,
                config           = config,
                info_api         = info_api,
                validation_api   = validation_api,
                context          = context,
                expects_reporter = False,
            )
            opcode_info = info_api.get_info_by_new(block.opcode)
            opcode_type = opcode_info.get_opcode_type(block=block, validation_api=validation_api)
            SRBlock.validate_opcode_type(
                opcode_type  = opcode_type,
                path         = current_path,
                config       = config,
                is_top_level = False,
                is_first     = (i == 0),
                is_last      = ((i+1) == len(self.blocks)),
            )


__all__ = [
    "FRBlock", "IRBlock", "IRInputValue", "IRBlockReference", 
    "SRScript", "SRBlock", "SRInputValue", "SRBlockAndTextInputValue", 
    "SRBlockAndDropdownInputValue", "SRBlockOnlyInputValue", "SRScriptInputValue",
]

