"""工作流视图。"""

import json
import time

from celery.result import AsyncResult
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import exceptions, renderers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    WorkflowBinding,
    WorkflowCallbackEvent,
    WorkflowCanvas,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeRun,
    WorkflowRun,
)
from .serializers import (
    WorkflowCanvasExecuteSelectionSerializer,
    WorkflowBindingSerializer,
    WorkflowCallbackEventSerializer,
    WorkflowCanvasCreateSerializer,
    WorkflowCanvasDetailSerializer,
    WorkflowCanvasGraphSerializer,
    WorkflowCanvasListSerializer,
    WorkflowDefinitionSerializer,
    WorkflowEdgeSerializer,
    WorkflowNodeExecuteSerializer,
    WorkflowNodeApplyResultSerializer,
    WorkflowNodeRunCreateSerializer,
    WorkflowNodeRunSerializer,
    WorkflowNodeRunUpdateSerializer,
    WorkflowNodeSerializer,
    WorkflowRunCreateSerializer,
    WorkflowRunDetailSerializer,
    WorkflowRunListSerializer,
)
from .services import apply_workflow_node_result
from .tasks import execute_workflow_node_task


class ServerSentEventRenderer(renderers.BaseRenderer):
    media_type = 'text/event-stream'
    format = 'event-stream'
    charset = 'utf-8'
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class WorkflowDefinitionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkflowDefinitionSerializer
    queryset = WorkflowDefinition.objects.all().select_related('created_by')
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['source_system', 'is_active', 'key']
    search_fields = ['key', 'name']
    ordering_fields = ['created_at', 'updated_at', 'version']
    ordering = ['key', '-version']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class WorkflowCanvasViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'project', 'series', 'definition']
    search_fields = ['name', 'description', 'external_canvas_id']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_queryset(self):
        return (
            WorkflowCanvas.objects
            .filter(created_by=self.request.user)
            .select_related('definition', 'project', 'series', 'created_by')
            .prefetch_related('nodes', 'edges')
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return WorkflowCanvasCreateSerializer
        if self.action == 'retrieve':
            return WorkflowCanvasDetailSerializer
        if self.action == 'graph':
            return WorkflowCanvasGraphSerializer
        return WorkflowCanvasListSerializer

    @action(detail=True, methods=['patch'])
    def graph(self, request, pk=None):
        canvas = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'canvas': canvas})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        detail = WorkflowCanvasDetailSerializer(canvas.refresh_from_db() or canvas, context=self.get_serializer_context())
        return Response(detail.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def execute_selection(self, request, pk=None):
        canvas = self.get_object()
        serializer = WorkflowCanvasExecuteSelectionSerializer(data=request.data, context={'canvas': canvas})
        serializer.is_valid(raise_exception=True)
        runs = serializer.save()

        queued_runs = []
        failed_runs = []
        for run in runs:
            try:
                task = execute_workflow_node_task.delay(str(run.id))
                run.refresh_from_db()
                if task and task.id and run.status in {'pending', 'queued'}:
                    update_fields = ['updated_at']
                    if not run.external_task_id:
                        run.external_task_id = task.id
                        update_fields.append('external_task_id')
                    if run.status == 'pending':
                        run.status = 'queued'
                        update_fields.append('status')
                    run.save(update_fields=update_fields)
                    if run.node_id:
                        WorkflowNode.objects.filter(id=run.node_id).update(
                            status='queued',
                            updated_at=timezone.now(),
                        )
                queued_runs.append(run)
            except Exception as exc:
                refreshed = WorkflowNodeRun.objects.select_related('node').get(id=run.id)
                refreshed.status = 'failed'
                refreshed.error_message = str(exc) or '任务入队失败'
                refreshed.completed_at = timezone.now()
                refreshed.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
                if refreshed.node_id:
                    WorkflowNode.objects.filter(id=refreshed.node_id).update(
                        status='failed',
                        updated_at=timezone.now(),
                    )
                failed_runs.append(refreshed)

        ordered_runs = []
        failed_run_map = {str(run.id): run for run in failed_runs}
        for run in runs:
            ordered_runs.append(failed_run_map.get(str(run.id), run))

        response_serializer = WorkflowNodeRunSerializer(ordered_runs, many=True, context=self.get_serializer_context())
        return Response({
            'runs': response_serializer.data,
            'summary': {
                'total_count': len(ordered_runs),
                'queued_count': len([run for run in ordered_runs if run.status == 'queued']),
                'failed_count': len([run for run in ordered_runs if run.status == 'failed']),
            },
        }, status=status.HTTP_201_CREATED)


class WorkflowNodeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkflowNodeSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['canvas', 'node_type', 'status', 'is_enabled']
    search_fields = ['node_key', 'title']
    ordering_fields = ['created_at', 'updated_at', 'node_key']
    ordering = ['created_at']

    def get_queryset(self):
        return WorkflowNode.objects.filter(canvas__created_by=self.request.user).select_related('canvas')

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        node = self.get_object()
        serializer = WorkflowNodeExecuteSerializer(data=request.data, context={'node': node})
        serializer.is_valid(raise_exception=True)
        run = serializer.save()
        task = execute_workflow_node_task.delay(str(run.id))
        run.refresh_from_db()
        node.refresh_from_db()
        if task and task.id and run.status in {'pending', 'running'}:
            update_fields = ['updated_at']
            if not run.external_task_id:
                run.external_task_id = task.id
                update_fields.append('external_task_id')
            if run.status == 'pending':
                run.status = 'queued'
                update_fields.append('status')
            run.save(update_fields=update_fields)
            if node.status == 'running':
                node.status = 'queued'
                node.save(update_fields=['status', 'updated_at'])
            run.refresh_from_db()
        response = WorkflowNodeRunSerializer(run, context=self.get_serializer_context())
        return Response(response.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def runs(self, request, pk=None):
        node = self.get_object()
        queryset = node.runs.select_related('canvas', 'node', 'workflow_run').prefetch_related('bindings').order_by('-sequence', '-created_at')
        serializer = WorkflowNodeRunSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


class WorkflowEdgeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkflowEdgeSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['canvas', 'source_node', 'target_node', 'is_enabled']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['created_at']

    def get_queryset(self):
        return WorkflowEdge.objects.filter(canvas__created_by=self.request.user).select_related('canvas', 'source_node', 'target_node')


class WorkflowRunViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'trigger_mode', 'project', 'series', 'definition']
    search_fields = ['external_run_id', 'current_node_key']
    ordering_fields = ['created_at', 'updated_at', 'started_at', 'completed_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            WorkflowRun.objects
            .filter(created_by=self.request.user)
            .select_related('definition', 'project', 'series', 'created_by')
            .prefetch_related('node_runs__bindings', 'bindings')
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return WorkflowRunCreateSerializer
        if self.action == 'retrieve':
            return WorkflowRunDetailSerializer
        return WorkflowRunListSerializer

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        workflow_run = self.get_object()
        workflow_run.status = 'running'
        workflow_run.started_at = workflow_run.started_at or timezone.now()
        workflow_run.error_message = ''
        workflow_run.save(update_fields=['status', 'started_at', 'error_message', 'updated_at'])
        return Response({'message': '工作流已启动', 'workflow_run_id': str(workflow_run.id)})

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        workflow_run = self.get_object()
        workflow_run.status = 'paused'
        workflow_run.save(update_fields=['status', 'updated_at'])
        return Response({'message': '工作流已暂停', 'workflow_run_id': str(workflow_run.id)})

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        workflow_run = self.get_object()
        workflow_run.status = 'running'
        workflow_run.save(update_fields=['status', 'updated_at'])
        return Response({'message': '工作流已恢复', 'workflow_run_id': str(workflow_run.id)})

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        workflow_run = self.get_object()
        workflow_run.status = 'pending'
        workflow_run.error_message = ''
        workflow_run.completed_at = None
        workflow_run.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
        workflow_run.node_runs.update(
            status='pending',
            error_message='',
            completed_at=None,
            started_at=None,
        )
        return Response({'message': '工作流已重置为待运行', 'workflow_run_id': str(workflow_run.id)})


class WorkflowNodeRunViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['workflow_run', 'node_key', 'node_type', 'status']
    search_fields = ['external_task_id', 'idempotency_key']
    ordering_fields = ['created_at', 'updated_at', 'sequence']
    ordering = ['workflow_run', 'sequence']

    def perform_content_negotiation(self, request, force=False):
        try:
            return super().perform_content_negotiation(request, force)
        except exceptions.NotAcceptable:
            accept_header = request.META.get('HTTP_ACCEPT', '')
            if 'text/event-stream' in accept_header:
                renderer = ServerSentEventRenderer()
                return (renderer, renderer.media_type)
            raise

    def get_queryset(self):
        return (
            WorkflowNodeRun.objects
            .filter(Q(canvas__created_by=self.request.user) | Q(workflow_run__created_by=self.request.user))
            .select_related('workflow_run', 'canvas', 'node')
            .prefetch_related('bindings')
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return WorkflowNodeRunCreateSerializer
        if self.action in ['update', 'partial_update']:
            return WorkflowNodeRunUpdateSerializer
        return WorkflowNodeRunSerializer

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        node_run = self.get_object()
        result = apply_workflow_node_result(node_run)
        serializer = WorkflowNodeApplyResultSerializer({
            'message': '节点结果已回填到 ai_story',
            'result': result,
            'node_run': node_run,
        })
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], renderer_classes=[ServerSentEventRenderer])
    def stream(self, request, pk=None):
        node_run = self.get_object()

        def event_stream():
            yield f"data: {json.dumps({'type': 'connected', 'node_run_id': str(node_run.id)}, ensure_ascii=False)}\n\n"
            last_payload = None
            last_task_state = None
            idle_count = 0
            for _ in range(600):
                refreshed = self.get_queryset().get(id=node_run.id)
                payload = {
                    'type': 'status',
                    'node_run_id': str(refreshed.id),
                    'task_id': refreshed.external_task_id or '',
                    'status': refreshed.status,
                    'node_type': refreshed.node_type,
                    'error_message': refreshed.error_message or '',
                    'normalized_output': refreshed.normalized_output or {},
                    'output_payload': refreshed.output_payload or {},
                    'started_at': refreshed.started_at.isoformat() if refreshed.started_at else None,
                    'completed_at': refreshed.completed_at.isoformat() if refreshed.completed_at else None,
                }
                changed = payload != last_payload
                if changed:
                    yield f'data: {json.dumps(payload, ensure_ascii=False)}\n\n'
                    last_payload = payload

                if refreshed.external_task_id:
                    task_state = AsyncResult(refreshed.external_task_id).state
                    if task_state in {'PENDING', 'RECEIVED', 'STARTED', 'RETRY', 'SUCCESS', 'FAILURE', 'REVOKED'}:
                        if task_state != last_task_state:
                            meta_payload = {
                                'type': 'task_state',
                                'node_run_id': str(refreshed.id),
                                'task_id': refreshed.external_task_id,
                                'task_state': task_state,
                            }
                            yield f'data: {json.dumps(meta_payload, ensure_ascii=False)}\n\n'
                            last_task_state = task_state
                            changed = True

                if refreshed.status in {'completed', 'failed', 'cancelled'}:
                    final_type = 'done' if refreshed.status == 'completed' else 'error'
                    final_payload = {
                        'type': final_type,
                        'node_run_id': str(refreshed.id),
                        'task_id': refreshed.external_task_id or '',
                        'status': refreshed.status,
                        'normalized_output': refreshed.normalized_output or {},
                        'output_payload': refreshed.output_payload or {},
                        'error': refreshed.error_message or '',
                    }
                    yield f'data: {json.dumps(final_payload, ensure_ascii=False)}\n\n'
                    break

                idle_count = 0 if changed else idle_count + 1
                time.sleep(3 if idle_count >= 3 else 1)

            yield f"data: {json.dumps({'type': 'stream_end', 'node_run_id': str(node_run.id)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream; charset=utf-8')
        response['Cache-Control'] = 'no-cache, no-transform'
        response['X-Accel-Buffering'] = 'no'
        return response


class WorkflowBindingViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkflowBindingSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['workflow_run', 'node_run', 'binding_type']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['created_at']

    def get_queryset(self):
        return (
            WorkflowBinding.objects
            .filter(Q(canvas__created_by=self.request.user) | Q(workflow_run__created_by=self.request.user))
            .select_related('workflow_run', 'canvas', 'node', 'node_run')
            .distinct()
        )


class WorkflowCallbackEventViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkflowCallbackEventSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['workflow_run', 'node_run', 'provider', 'process_status']
    ordering_fields = ['received_at', 'processed_at']
    ordering = ['-received_at']

    def get_queryset(self):
        return (
            WorkflowCallbackEvent.objects
            .filter(Q(canvas__created_by=self.request.user) | Q(workflow_run__created_by=self.request.user))
            .select_related('workflow_run', 'canvas', 'node_run')
            .distinct()
        )

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        instance = self.get_queryset().get(pk=pk)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        response_serializer = self.get_serializer(event)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
