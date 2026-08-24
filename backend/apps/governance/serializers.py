"""Governance serializers."""
from __future__ import annotations

from rest_framework import serializers

from apps.governance.checksums import canonical_config_hash, validate_artifact_path
from apps.governance.models import (
    AIModel,
    AIModelVersion,
    AlgorithmDefinition,
    AlgorithmVersion,
    ModelArtifact,
    ModelEvaluation,
    StoredArtifact,
)


class AIModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = ["id", "family", "task", "provider", "description", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class AIModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModelVersion
        fields = [
            "id", "model", "version", "provenance", "license", "source_url",
            "config", "input_spec", "output_schema_version", "class_map",
            "benchmark_summary", "is_active", "imported_at",
        ]
        read_only_fields = ["id", "imported_at", "is_active"]


class ModelArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelArtifact
        fields = ["id", "model_version", "kind", "path", "checksum_sha256", "size_bytes", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_path(self, value: str) -> str:
        try:
            validate_artifact_path(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value


class ModelEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelEvaluation
        fields = ["id", "model_version", "dataset_ref", "metrics", "provenance_note", "created_at"]
        read_only_fields = ["id", "created_at"]


class AlgorithmDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlgorithmDefinition
        fields = ["id", "key", "name", "category", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


class AlgorithmVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlgorithmVersion
        fields = ["id", "definition", "version", "config", "config_hash", "description", "is_active", "created_at"]
        read_only_fields = ["id", "config_hash", "created_at", "is_active"]

    def create(self, validated_data):
        validated_data["config_hash"] = canonical_config_hash(validated_data.get("config", {}))
        return super().create(validated_data)


class StoredArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoredArtifact
        fields = ["id", "category", "path", "checksum_sha256", "size_bytes", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_path(self, value: str) -> str:
        try:
            validate_artifact_path(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value
