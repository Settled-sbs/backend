"""
Small helper to build `execute()`-style `msg.data` envelopes compatible with
`FirewallHook._decodeTarget`.

Layout produced (matching the contract's docstring):
  [0:4] selector
  [4:36] ExecutionMode (32 bytes) - first byte = callType (0=single)
  [36:68] offset (32 bytes) pointing relative to byte 4 to the bytes param
  at (4 + offset):
    [0:32] length of bytes
    [32:...] payload: for CALLTYPE_SINGLE -> target(20) ++ value(32) ++ calldata

The helper builds this and returns raw `bytes`.
"""


CALLTYPE_SINGLE = 0


def build_execute_msgdata(
    selector: bytes,
    target: str,
    value: int,
    call_data: bytes,
    calltype: int = CALLTYPE_SINGLE,
) -> bytes:
    """Return bytes representing the full `msg.data` envelope.

    - `selector` must be 4 bytes.
    - `target` is an address hex string.
    - `call_data` is raw calldata for the inner call.
    """
    assert len(selector) == 4

    # ExecutionMode: 32 bytes where first byte is callType
    exec_mode = bytes([calltype]) + b"" * 31

    # We'll place the bytes param immediately after the 3 header words
    # header size after selector: ExecutionMode (32) + offset (32) = 64 bytes
    # offset is relative to byte 4
    offset = 64
    offset_word = offset.to_bytes(32, "big")

    # Build inner payload: target(20) + value(32) + calldata
    target_bytes = bytes.fromhex(target[2:]) if target.startswith("0x") else bytes.fromhex(target)
    assert len(target_bytes) == 20
    value_word = value.to_bytes(32, "big")
    payload = target_bytes + value_word + call_data

    # ABI-encode bytes parameter: first 32 bytes = length, then data (padded to 32)
    length_word = len(payload).to_bytes(32, "big")
    # pad payload to 32-byte multiple
    pad_len = (32 - (len(payload) % 32)) % 32
    payload_padded = payload + (b"\x00" * pad_len)

    # final msgData: selector + exec_mode + offset_word + length_word + payload_padded
    msgdata = selector + exec_mode + offset_word + length_word + payload_padded
    return msgdata


if __name__ == "__main__":
    # Example usage
    selector = b"\x12\x34\x56\x78"
    target = "0x" + "11" * 20
    cd = b"\x90\x91\x92"
    md = build_execute_msgdata(selector, target, 0, cd)
    print(md.hex())
