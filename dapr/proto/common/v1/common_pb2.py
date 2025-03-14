# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: dapr/proto/common/v1/common.proto
# Protobuf Python Version: 4.25.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n!dapr/proto/common/v1/common.proto\x12\x14\x64\x61pr.proto.common.v1\x1a\x19google/protobuf/any.proto\"\xd0\x01\n\rHTTPExtension\x12\x36\n\x04verb\x18\x01 \x01(\x0e\x32(.dapr.proto.common.v1.HTTPExtension.Verb\x12\x13\n\x0bquerystring\x18\x02 \x01(\t\"r\n\x04Verb\x12\x08\n\x04NONE\x10\x00\x12\x07\n\x03GET\x10\x01\x12\x08\n\x04HEAD\x10\x02\x12\x08\n\x04POST\x10\x03\x12\x07\n\x03PUT\x10\x04\x12\n\n\x06\x44\x45LETE\x10\x05\x12\x0b\n\x07\x43ONNECT\x10\x06\x12\x0b\n\x07OPTIONS\x10\x07\x12\t\n\x05TRACE\x10\x08\x12\t\n\x05PATCH\x10\t\"\x96\x01\n\rInvokeRequest\x12\x0e\n\x06method\x18\x01 \x01(\t\x12\"\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32\x14.google.protobuf.Any\x12\x14\n\x0c\x63ontent_type\x18\x03 \x01(\t\x12;\n\x0ehttp_extension\x18\x04 \x01(\x0b\x32#.dapr.proto.common.v1.HTTPExtension\"J\n\x0eInvokeResponse\x12\"\n\x04\x64\x61ta\x18\x01 \x01(\x0b\x32\x14.google.protobuf.Any\x12\x14\n\x0c\x63ontent_type\x18\x02 \x01(\t\"*\n\rStreamPayload\x12\x0c\n\x04\x64\x61ta\x18\x01 \x01(\x0c\x12\x0b\n\x03seq\x18\x02 \x01(\x04\"\xf8\x01\n\tStateItem\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\x0c\x12(\n\x04\x65tag\x18\x03 \x01(\x0b\x32\x1a.dapr.proto.common.v1.Etag\x12?\n\x08metadata\x18\x04 \x03(\x0b\x32-.dapr.proto.common.v1.StateItem.MetadataEntry\x12\x33\n\x07options\x18\x05 \x01(\x0b\x32\".dapr.proto.common.v1.StateOptions\x1a/\n\rMetadataEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01\"\x15\n\x04\x45tag\x12\r\n\x05value\x18\x01 \x01(\t\"\xef\x02\n\x0cStateOptions\x12H\n\x0b\x63oncurrency\x18\x01 \x01(\x0e\x32\x33.dapr.proto.common.v1.StateOptions.StateConcurrency\x12H\n\x0b\x63onsistency\x18\x02 \x01(\x0e\x32\x33.dapr.proto.common.v1.StateOptions.StateConsistency\"h\n\x10StateConcurrency\x12\x1b\n\x17\x43ONCURRENCY_UNSPECIFIED\x10\x00\x12\x1b\n\x17\x43ONCURRENCY_FIRST_WRITE\x10\x01\x12\x1a\n\x16\x43ONCURRENCY_LAST_WRITE\x10\x02\"a\n\x10StateConsistency\x12\x1b\n\x17\x43ONSISTENCY_UNSPECIFIED\x10\x00\x12\x18\n\x14\x43ONSISTENCY_EVENTUAL\x10\x01\x12\x16\n\x12\x43ONSISTENCY_STRONG\x10\x02\"\xad\x01\n\x11\x43onfigurationItem\x12\r\n\x05value\x18\x01 \x01(\t\x12\x0f\n\x07version\x18\x02 \x01(\t\x12G\n\x08metadata\x18\x03 \x03(\x0b\x32\x35.dapr.proto.common.v1.ConfigurationItem.MetadataEntry\x1a/\n\rMetadataEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01\x42i\n\nio.dapr.v1B\x0c\x43ommonProtosZ/github.com/dapr/dapr/pkg/proto/common/v1;common\xaa\x02\x1b\x44\x61pr.Client.Autogen.Grpc.v1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'dapr.proto.common.v1.common_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  _globals['DESCRIPTOR']._options = None
  _globals['DESCRIPTOR']._serialized_options = b'\n\nio.dapr.v1B\014CommonProtosZ/github.com/dapr/dapr/pkg/proto/common/v1;common\252\002\033Dapr.Client.Autogen.Grpc.v1'
  _globals['_STATEITEM_METADATAENTRY']._options = None
  _globals['_STATEITEM_METADATAENTRY']._serialized_options = b'8\001'
  _globals['_CONFIGURATIONITEM_METADATAENTRY']._options = None
  _globals['_CONFIGURATIONITEM_METADATAENTRY']._serialized_options = b'8\001'
  _globals['_HTTPEXTENSION']._serialized_start=87
  _globals['_HTTPEXTENSION']._serialized_end=295
  _globals['_HTTPEXTENSION_VERB']._serialized_start=181
  _globals['_HTTPEXTENSION_VERB']._serialized_end=295
  _globals['_INVOKEREQUEST']._serialized_start=298
  _globals['_INVOKEREQUEST']._serialized_end=448
  _globals['_INVOKERESPONSE']._serialized_start=450
  _globals['_INVOKERESPONSE']._serialized_end=524
  _globals['_STREAMPAYLOAD']._serialized_start=526
  _globals['_STREAMPAYLOAD']._serialized_end=568
  _globals['_STATEITEM']._serialized_start=571
  _globals['_STATEITEM']._serialized_end=819
  _globals['_STATEITEM_METADATAENTRY']._serialized_start=772
  _globals['_STATEITEM_METADATAENTRY']._serialized_end=819
  _globals['_ETAG']._serialized_start=821
  _globals['_ETAG']._serialized_end=842
  _globals['_STATEOPTIONS']._serialized_start=845
  _globals['_STATEOPTIONS']._serialized_end=1212
  _globals['_STATEOPTIONS_STATECONCURRENCY']._serialized_start=1009
  _globals['_STATEOPTIONS_STATECONCURRENCY']._serialized_end=1113
  _globals['_STATEOPTIONS_STATECONSISTENCY']._serialized_start=1115
  _globals['_STATEOPTIONS_STATECONSISTENCY']._serialized_end=1212
  _globals['_CONFIGURATIONITEM']._serialized_start=1215
  _globals['_CONFIGURATIONITEM']._serialized_end=1388
  _globals['_CONFIGURATIONITEM_METADATAENTRY']._serialized_start=772
  _globals['_CONFIGURATIONITEM_METADATAENTRY']._serialized_end=819
# @@protoc_insertion_point(module_scope)
