from typing import Callable

from pypenguin.utility import grepr_dataclass, PypenguinEnum

class SpecialCaseType(PypenguinEnum):
    """
    Currently impletented kinds of Special Cases. Documentation is included in the source code
    """
    
    ######################################################
    #                    Data Handlers                   # 
    ######################################################
    
    GET_OPCODE_TYPE = 0
    # evaluate opcode type
    # is called when opcode_info.opcode_type is DYNAMIC
    # should NEVER return MENU (or any other pseudo opcode type)
    """
    def example(
        block: "SRBlock|TRBlock", validation_api: "ValidationAPI"
    ) -> OpcodeType:
        ...
    """

    GET_ALL_INPUT_IDS_TYPES = 1
    # map new and old input id to input type
    # -> DualKeyDict[old, new, InpuType]
    # ficapi will be None for a TRBlock or SRBlock and the block api for a FRBlock
    """
    def example(
        block: "FRBlock|TRBlock|SRBlock", ficapi: "FIConversionAPI|None"
    ) -> DualKeyDict[str, str, InputType]:
        ...
    """
    
    
    ######################################################
    #                 Behaviour Handlers                 # 
    ######################################################
    
    PRE_FR_STEP = 2 # execure before FRBlock.step
    """
    def example(block: "FRBlock", ficapi: "FIConversionAPI") -> "FRBlock":
        ...
    """
     
    FR_STEP = 3 # execute instead of FRBlock.step
    """
    def example(block: "FRBlock", ficapi: "FIConversionAPI") -> "TRBlock":
        ...
    """
    
    POST_VALIDATION = 4 # execute after SRBlock.validate
    """
    def example(path: list, block: "SRBlock") -> None:
        ...
    """    

@grepr_dataclass(grepr_fields=["type", "function"])
class SpecialCase:
    """
    Special Cases allows for custom behaviour for special blocks
    """

    type: SpecialCaseType
    function: Callable
    
    def call(self, *args, **kwargs):
        """
        Call a special case and get its return value. Arguments depend on SpecialCaseType
        Parameters:
            *args: positional arguments forwarded to the function
            **kwargs: keyword arguments forwarded to the function

        Returns:
            the return value of the function
        """
        return self.function(*args, **kwargs)


__all__ = ["SpecialCaseType", "SpecialCase"]

