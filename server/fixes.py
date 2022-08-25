def fix_proto_uint():
    from pure_protobuf.types import uint, uint32
    import pure_protobuf.serializers as ser
    _rv = ser.read_varint
    def rv(*args, **kwargs):
        value = int(_rv(*args, **kwargs))
        if (1 << 64) - 20000 <= value < (1 << 64): value -= (1 << 64)
        return uint(value)
    ser.read_varint = rv
    class pUnsignedVarintSerializer(ser.UnsignedVarintSerializer):
        def validate(self, value):
            if value is None: return
            if value < 0: value += (1 << 64)
            return super().validate(value)
        def dump(self, value, io):
            if value < 0: value += (1 << 64)
            return super().dump(value, io)
    class pUnsignedInt32Serializer(ser.UnsignedInt32Serializer):
        def validate(self, value):
            pUnsignedVarintSerializer().validate(value)
    ser.UnsignedVarintSerializer = pUnsignedVarintSerializer
    ser.unsigned_varint_serializer = pUnsignedVarintSerializer()
    ser.UnsignedInt32Serializer = pUnsignedInt32Serializer
    import pure_protobuf.dataclasses_ as dc
    dc.SERIALIZERS[uint32] = pUnsignedInt32Serializer()