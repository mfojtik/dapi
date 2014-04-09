from django.contrib.auth.models import User
from dapi.models import MetaDap, Dap
from rest_framework import serializers


class UserSerializer(serializers.HyperlinkedModelSerializer):
    fedora_username = serializers.Field(source='profile.fedora_username')
    github_username = serializers.Field(source='profile.github_username')

    class Meta:
        model = User
        fields = (
            'url',
            'id',
            'username',
            'metadap_set',
            'codap_set',
            'fedora_username',
            'github_username',
        )
        #lookup_field = 'username'


class MetaDapSerializer(serializers.HyperlinkedModelSerializer):
    reports = serializers.Field(source='get_unsolved_reports_count')
    tags = serializers.Field(source='tags.all')
    similar_daps = serializers.Field(source='similar_active_daps')

    class Meta:
        model = MetaDap
        fields = (
            'url',
            'id',
            'package_name',
            'user',
            'active',
            'rank_count',
            'average_rank',
            'latest',
            'latest_stable',
            'reports',
            'dap_set',
            'comaintainers',
            'tags',
            'similar_daps',
        )


class DapSerializer(serializers.HyperlinkedModelSerializer):
    package_name = serializers.Field(source='metadap.package_name')
    authors = serializers.Field(source='get_authors')
    is_pre = serializers.Field(source='is_pre')
    is_latest = serializers.Field(source='is_latest')
    is_latest_stable = serializers.Field(source='is_latest_stable')
    reports = serializers.Field(source='metadap.get_unsolved_reports_count')

    class Meta:
        model = Dap
        fields = (
            'url',
            'id',
            'metadap',
            'package_name',
            'version',
            'license',
            'summary',
            'description',
            'authors',
            'homepage',
            'bugreports',
            'is_pre',
            'is_latest',
            'is_latest_stable',
            'reports',
        )
