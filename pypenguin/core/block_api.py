from typing      import TYPE_CHECKING
from dataclasses import dataclass, field

from pypenguin.utility import GreprClass, FirstToInterConversionError, ValidationError

from pypenguin.core.custom_block import SRCustomBlockOpcode

if TYPE_CHECKING:
    from pypenguin.core.block          import FRBlock, SRBlock, SRScript
    from pypenguin.core.comment        import SRComment
    from pypenguin.core.block_mutation import FRCustomBlockMutation, SRCustomBlockMutation

@dataclass(repr=False)
class FICAPI(GreprClass):
    """
    An API which allows the access to other blocks in the same target during **c**onversion from **f**irst to **i**ntermediate representation.
    """
    _grepr = True
    _grepr_fields = ["blocks", "scheduled_block_deletions"]

    blocks: dict[str, "FRBlock"]
    block_comments: dict[str, "SRComment"]
    scheduled_block_deletions: list[str] = field(default_factory=list)

    def get_all_blocks(self) -> dict[str, "FRBlock"]:
        """
        Get all blocks in the same target
        
        Returns:
            all blocks in the target 
        """
        return self.blocks
    
    def get_block(self, block_id: str) -> "FRBlock":
        """
        Get a block in the same target by block id
        
        Returns:
            the requested block
        """
        return self.get_all_blocks()[block_id]
    
    def schedule_block_deletion(self, block_id: str) -> None:
        """
        Order a block to be deleted. 
        It will no longer be present in Temporary and Second Representation.
        
        Args:
            block_id: the id of the block to be deleted
        
        Returns:
            None
        """
        self.scheduled_block_deletions.append(block_id)

    def get_cb_mutation(self, proccode: str) -> "FRCustomBlockMutation":
        """
        Get a custom block mutation by its procedure code
        
        Args:
            proccode: the procedure code of the desired mutation
        
        Returns:
            the custom block mutation
        """
        from pypenguin.core.block_mutation import FRCustomBlockMutation
        for block in self.blocks.values():
            if not isinstance(block.mutation, FRCustomBlockMutation): continue
            if block.mutation.proccode == proccode:
                return block.mutation
        raise FirstToInterConversionError(f"Mutation of proccode {repr(proccode)} not found.")

    def get_comment(self, comment_id: str) -> "SRComment":
        """
        Get a comment by id
        
        Args:
            comment_id: the id of the desired comment
        
        Returns:
            the comment
        """
        return self.block_comments[comment_id]

@dataclass(repr=False)
class ValidationAPI(GreprClass):
    """
    An API which allows the access to other blocks in the same target during validation.
    """
    _grepr = True
    _grepr_fields = ["scripts", "cb_mutations:"]

    scripts: dict[str, "SRScript"]
    cb_mutations: dict[SRCustomBlockOpcode, "SRCustomBlockMutation"] = field(init=False)
    # Safe access is needed because blocks haven't actually been validated yet
    
    def __post_init__(self) -> None:
        """
        Fetch and store custom block mutations for later.
        
        Returns:
            None
        """
        from pypenguin.core.block_mutation import SRCustomBlockMutation
        all_blocks = self.get_all_blocks()
        self.cb_mutations = {}
        for block in all_blocks:
            if isinstance(getattr(block, "mutation", None), SRCustomBlockMutation):
                if hasattr(block.mutation, "custom_opcode"):
                    self.cb_mutations[block.mutation.custom_opcode] = block.mutation

    def get_all_blocks(self) -> list["SRBlock"]:
        """
        Get all blocks in the same target
        
        Returns:
            all blocks in the target 
        """
        from pypenguin.core.block import SRBlock
        def recursive_block_search(block: "SRBlock") -> None:
            blocks.append(block)
            if not isinstance(getattr(block, "inputs", None), dict):
                return
            for input in block.inputs.values(): 
                if isinstance(getattr(input, "block", None), SRBlock):
                    recursive_block_search(input.block)
                if isinstance(getattr(input, "blocks", None), list):
                    [recursive_block_search(sub_block) for sub_block in input.blocks if isinstance(sub_block, SRBlock)]
                            
        blocks = []
        for script in self.scripts:
            for block in script.blocks:
                recursive_block_search(block)
        return blocks
    
    def get_cb_mutation(self, custom_opcode: SRCustomBlockOpcode) -> "FRCustomBlockMutation":
        """
        Get a custom block mutation by its custom opcode
        
        Args:
            custom_opcode: the custom opcode of the desired mutation
        
        Returns:
            the custom block mutation
        """
        if custom_opcode in self.cb_mutations:
            return self.cb_mutations[custom_opcode]
        raise ValidationError(f"Mutation of custom_opcode {custom_opcode} not found.")

