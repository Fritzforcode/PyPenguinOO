# Utility functions

def grepr(obj, annotate_fields=True, include_attributes=False, *, indent=4):
    def _grepr(obj, level=0):
        is_compatible = bool(getattr(obj, "_grepr", False))
        if indent is not None:
            level += 1
            prefix = '\n' + indent * level
            sep = ',\n' + indent * level
            end_sep = ',\n' + indent * (level-1)
        else:
            prefix = ''
            sep = ', '
            end_sep = ""
        if isinstance(obj, list):
            if not obj:
                return '[]', True
            return '[%s%s%s]' % (prefix, sep.join(_grepr(x, level)[0] for x in obj), end_sep), False
        if isinstance(obj, tuple):
            if not obj:
                return '()', True
            if len(obj) <= 2:
                return '(%s)' % (", ".join(_grepr(x, level)[0] for x in obj)), False
            else:
                return '(%s%s%s)' % (prefix, sep.join(_grepr(x, level)[0] for x in obj), end_sep), False
        elif isinstance(obj, dict):
            if not obj:
                return '{}', True
            args = [f'{_grepr(key, level)[0]}: {_grepr(value, level)[0]}' for key,value in obj.copy().items()]    
            return '{%s%s%s}' % (prefix, sep.join(args), end_sep), False
        elif isinstance(obj, str):
            return f'"{obj.replace('"', '\\"')}"', True
        elif isinstance(obj, DualKeyDict):
            if not obj:
                return 'DKD{}', True
            args = []
            for key1, key2, value in obj.items_key1_key2():
                key1_str, _ = _grepr(key1, level)
                key2_str, _ = _grepr(key2, level)
                value_str, _ = _grepr(value, level)
                args.append(f'{key1_str} / {key2_str}: {value_str}')
            return 'DKD{%s%s%s}' % (prefix, sep.join(args), end_sep), False
        elif is_compatible:
            cls = type(obj)
            args = []
            allsimple = True
            keywords = annotate_fields
            for name in obj._grepr_fields:
                if not hasattr(obj, name):
                    continue
                value = getattr(obj, name)
                value, simple = _grepr(value, level)
                allsimple = allsimple and simple
                if keywords:
                    args.append('%s=%s' % (name, value))
                else:
                    args.append(value)
            if include_attributes and obj._attributes:
                for name in obj._attributes:
                    try:
                        value = getattr(obj, name)
                    except AttributeError:
                        continue
                    if value is None and getattr(cls, name, ...) is None:
                        continue
                    value, simple = _grepr(value, level)
                    allsimple = allsimple and simple
                    args.append('%s=%s' % (name, value))
            class_name = getattr(obj, "_grepr_class_name", obj.__class__.__name__)
            if allsimple and len(args) <= 3:
                return '%s(%s)' % (class_name, ', '.join(args)), not args
            return '%s(%s%s%s)' % (class_name, prefix, sep.join(args), end_sep), False
        return repr(obj), True
 
    is_compatible = bool(getattr(obj, "_grepr", False))
    if not(is_compatible) and not(isinstance(obj, (list, tuple, dict, str, DualKeyDict))):
        return repr(obj)
    if indent is not None and not isinstance(indent, str):
        indent = ' ' * indent
    return _grepr(obj)[0]

# Files
import zipfile
import os
from pypenguin.utility.errors import PathError

def read_all_files_of_zip(zip_path) -> dict[str, bytes]:
    zip_path = ensure_correct_path(zip_path)
    contents = {}
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        for file_name in zip_ref.namelist():
            with zip_ref.open(file_name) as file_ref:
                contents[file_name] = file_ref.read()
    return contents

def ensure_correct_path(_path: str, target_folder_name: str = "pypenguin") -> str:
    if target_folder_name is not None:
        initial_path = __file__
        current_path = os.path.normpath(initial_path)

        while True:
            base_name = os.path.basename(current_path)
            
            if base_name == target_folder_name and os.path.isdir(current_path):
                break
            
            parent_path = os.path.dirname(current_path)
            
            if parent_path == current_path:
                raise PathError(f"Target folder '{target_folder_name}' not found in the _path '{initial_path}'")
            
            current_path = parent_path

        final_path = os.path.join(current_path, _path)
        return final_path

# Utility Classes
from enum        import Enum
from typing      import TypeVar, Generic, Iterator
from dataclasses import dataclass

class PypenguinEnum(Enum):
    def __repr__(self) -> str:
        return self.__class__.__name__ + "." + self.name

def grepr_dataclass(*, grepr_fields: list[str], parent_cls: type|None = None, 
        init: bool = True, eq: bool = True, order: bool = False, 
        unsafe_hash: bool = False, frozen: bool = False, 
        match_args: bool = True, kw_only: bool = False, 
        slots: bool = False, weakref_slot: bool = False,
    ):
    """
    A decorator which combines @dataclass and a good representation system.
    Args:
        grepr_fields: fields for the good repr implementation
        parent_cls: class whose fields will also be included in the good repr impletementation
        init...: dataclass parameters
    """
    def decorator(cls: type):
        def __repr__(self) -> str:
            return grepr(self)
        cls.__repr__ = __repr__
        cls._grepr = True
        if parent_cls is None:
            cls._grepr_fields = grepr_fields
        else:
            cls._grepr_fields = parent_cls._grepr_fields + grepr_fields
        cls = dataclass(cls, 
            init=init, repr=False, eq=eq,
            order=order, unsafe_hash=unsafe_hash, frozen=frozen,
            match_args=match_args, kw_only=kw_only,
            slots=slots, weakref_slot=weakref_slot,
        )
        return cls
    return decorator

K1 = TypeVar("K1")
K2 = TypeVar("K2")
V  = TypeVar("V" )

class DualKeyDict(Generic[K1, K2, V]):
    """
    A custom dictionary system, which allows access by key1 or key2
    """
    def __init__(self, data: dict[tuple[K1, K2], V] | None = None, /) -> None:
        self._values  : dict[K1, V ] = {}
        self._k2_to_k1: dict[K2, K1] = {}
        self._k1_to_k2: dict[K1, K2] = {}
        if data is not None:
            for keys, value in data.items():
                key1, key2 = keys
                self.set(key1, key2, value)

    @classmethod
    def from_same_keys(cls, data: dict[K1, V]) -> "DualKeyDict[K1, K1, V]":
        return DualKeyDict({
            (key, key): value for key, value in data.items()
        })

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DualKeyDict):
            return NotImplemented
        return (self._values == other._values) and (self._k2_to_k1 == other._k2_to_k1) and (self._k1_to_k2 == other._k1_to_k2)

    def __repr__(self) -> str:
        return grepr(self)

    def set(self, key1: K1, key2: K2, value: V) -> None:
        self._values[key1] = value
        self._k2_to_k1[key2] = key1
        self._k1_to_k2[key1] = key2

    def get_by_key1(self, key1: K1) -> V:
        return self._values[key1]

    def get_by_key2(self, key2: K2) -> V:
        key1 = self.get_key1_for_key2(key2)
        return self._values[key1]

    def get_key1_for_key2(self, key2: K2) -> K1:
        return self._k2_to_k1[key2]

    def get_key2_for_key1(self, key1: K1) -> K2:
        return self._k1_to_k2[key1]

    def has_key1(self, key1: K1) -> bool:
        return key1 in self._values
    
    def has_key2(self, key2: K2) -> bool:
        return key2 in self._k2_to_k1

    # Dict-like behavior (explicitly discouraged)
    def __iter__(self):
        raise NotImplementedError("Don't iterate DualKeyDict directly. Use keys_key1, keys_key2, values, items_key1, items_key2 etc")

    def __contains__(self, key: object) -> bool:
        raise NotImplementedError("Don't check whether a DualKeyDict contains something like a normal dict. Use has_key1 or has_key2 instead")

    def __len__(self) -> int:
        return len(self._values)

    # Iteration methods
    def keys_key1(self) -> Iterator[K1]:
        return self._values.keys()
    
    def keys_key2(self) -> Iterator[K2]:
        return self._k2_to_k1.keys()
    
    def keys_key1_key2(self) -> Iterator[tuple[K1, K2]]:
        return self._k1_to_k2.items()
    
    def values(self) -> Iterator[V]:
        return self._values.values()
    
    def items_key1(self) -> Iterator[tuple[K1, V]]:
        return self._values.items()

    def items_key2(self) -> Iterator[tuple[K2, V]]:
        for key2 in self._k2_to_k1.keys():
            yield (key2, self.get_by_key2(key2))
    
    def items_key1_key2(self) -> Iterator[tuple[K1, K2, V]]:
        for key2, key1 in self._k2_to_k1.items():
            yield (key1, key2, self.get_by_key1(key1))

# Data Functions
from difflib import SequenceMatcher
from hashlib import sha256

TOKEN_CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!#%()*+,-./:;=?@[]^_`{|}~"

def remove_duplicates(items: list) -> list:
    seen = []
    result = []
    for item in items:
        if item not in seen:
            seen.append(item)
            result.append(item)
    return result

def lists_equal_ignore_order(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False

    b_copy = b[:]
    for item in a:
        try:
            b_copy.remove(item)  # uses __eq__, safe for mutable objects
        except ValueError:
            raise Exception(item)
            return False
    return not b_copy

def get_closest_matches(string, possible_values: list[str], n: int) -> list[str]:
    similarity_scores = [(item, SequenceMatcher(None, string, item).ratio()) for item in possible_values]
    sorted_matches = sorted(similarity_scores, key=lambda x: x[1], reverse=True)
    return [i[0] for i in sorted_matches[:n]]   

def tuplify(obj):
    if isinstance(obj, list):
        return tuple(tuplify(item) for item in obj)
    elif isinstance(obj, dict):
        return {tuplify(key): tuplify(value) for key, value in obj.items()}
    elif isinstance(obj, (set, tuple)):
        return type(obj)(tuplify(item) for item in obj)
    else:
        return obj

def string_to_sha256(primary: str, secondary: str|None=None) -> str:
    def _string_to_sha256(input_string: str, digits: int) -> str:
        hex_hash = sha256(input_string.encode()).hexdigest()

        result = []
        for i in range(digits):
            chunk = hex_hash[i * 2:(i * 2) + 2]
            index = int(chunk, 16) % len(TOKEN_CHARSET)
            result.append(TOKEN_CHARSET[index])
        return ''.join(result)

    if secondary is None:
        return _string_to_sha256(primary, digits=20)
    else:
        return _string_to_sha256(primary, digits=16) + _string_to_sha256(secondary, digits=4)


__all__ = [
    "grepr", "read_all_files_of_zip", "ensure_correct_path", 
    "PypenguinEnum", "grepr_dataclass", "DualKeyDict", 
    "remove_duplicates", "lists_equal_ignore_order", "get_closest_matches", "tuplify", "string_to_sha256",
]

