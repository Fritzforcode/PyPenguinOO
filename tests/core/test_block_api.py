from pytest import fixture, raises
from copy   import deepcopy

from pypenguin.utility import FirstToInterConversionError, lists_equal_ignore_order

from pypenguin.core.block_api      import FICAPI, ValidationAPI
from pypenguin.core.block_mutation import (
    SRCustomBlockMutation
)
from pypenguin.core.custom_block   import (
    SRCustomBlockOptype,
)

from tests.core.constants import (
    ALL_FR_BLOCKS, ALL_SR_COMMENTS, ALL_SR_SCRIPTS, ALL_SR_BLOCKS, SR_BLOCK_CUSTOM_OPCODE,
)

@fixture
def ficapi():
    return FICAPI(
        blocks=ALL_FR_BLOCKS,
        block_comments=ALL_SR_COMMENTS,
    )

@fixture
def vapi():
    return ValidationAPI(scripts=ALL_SR_SCRIPTS)


def test_ficapi_get_all_blocks(ficapi: FICAPI):
    assert ficapi.get_all_blocks() == ALL_FR_BLOCKS

def test_ficapi_get_blocks(ficapi: FICAPI):
    assert ficapi.get_block("d") == ALL_FR_BLOCKS["d"]

def test_ficapi_schedule_block_deletion(ficapi: FICAPI):
    ficapi_copy = deepcopy(ficapi)
    ficapi_copy.schedule_block_deletion("z")
    assert ficapi_copy.scheduled_block_deletions == ["z"]

def test_ficapi_get_cb_mutation(ficapi: FICAPI):
    assert ficapi.get_cb_mutation("do sth text %s and bool %b") == ALL_FR_BLOCKS["a"].mutation
    with raises(FirstToInterConversionError):
        ficapi.get_cb_mutation("some %s proccode")

def test_ficapi_get_comment(ficapi: FICAPI):
    assert ficapi.get_comment("j") == ALL_SR_COMMENTS["j"]


def test_vapi_post_init(vapi: ValidationAPI):
    cb_mutations = {
        SR_BLOCK_CUSTOM_OPCODE: SRCustomBlockMutation(
            custom_opcode=SR_BLOCK_CUSTOM_OPCODE,
            no_screen_refresh=False,
            optype=SRCustomBlockOptype.NUMBER_REPORTER,
            color1="#FF6680",
            color2="#FF4D6A",
            color3="#FF3355",
        ),
    }
    assert vapi.cb_mutations == cb_mutations


def test_vapi_get_all_blocks(vapi: ValidationAPI):
    assert lists_equal_ignore_order(vapi.get_all_blocks(), ALL_SR_BLOCKS)

def test_vapi_get_cb_mutation(vapi: ValidationAPI):
    assert vapi.get_cb_mutation(SR_BLOCK_CUSTOM_OPCODE) == vapi.cb_mutations[SR_BLOCK_CUSTOM_OPCODE]


