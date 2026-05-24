from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from types import SimpleNamespace
from unittest.mock import patch

from apps.content.models import ContentRewrite, GeneratedImage, Storyboard
from apps.projects.models import Project, ProjectStage, Series
from apps.workflows.models import WorkflowCallbackEvent, WorkflowCanvas, WorkflowEdge, WorkflowNode, WorkflowNodeRun, WorkflowRun


User = get_user_model()


def initialize_project(project):
    for stage_type in ['rewrite', 'asset_extraction', 'storyboard', 'image_generation', 'multi_grid_image', 'camera_movement', 'video_generation', 'image_edit']:
        ProjectStage.objects.create(project=project, stage_type=stage_type, status='pending')
    ContentRewrite.objects.create(project=project, original_text=project.original_topic)


class WorkflowCallbackAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='workflow-user', password='secret123')
        self.client.force_authenticate(self.user)
        self.series = Series.objects.create(name='测试作品', description='desc', user=self.user)
        self.project = Project.objects.create(
            user=self.user,
            series=self.series,
            episode_number=1,
            sort_order=1,
            episode_title='第1集',
            name='第1集',
            original_topic='原始文案',
        )
        initialize_project(self.project)
        self.workflow_run = WorkflowRun.objects.create(project=self.project, series=self.series, created_by=self.user)
        self.canvas = WorkflowCanvas.objects.create(
            name='测试画板',
            project=self.project,
            series=self.series,
            created_by=self.user,
            status='active',
        )
        self.rewrite_node = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='rewrite_node',
            node_type='rewrite',
            title='改写',
            status='completed',
        )
        self.storyboard_node = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='storyboard_node',
            node_type='storyboard',
            title='分镜',
            status='completed',
        )
        WorkflowEdge.objects.create(
            canvas=self.canvas,
            edge_key='edge-1',
            source_node=self.rewrite_node,
            target_node=self.storyboard_node,
        )
        self.node_run = WorkflowNodeRun.objects.create(
            workflow_run=self.workflow_run,
            canvas=self.canvas,
            node=self.rewrite_node,
            node_key='rewrite_node',
            node_type='rewrite',
            status='waiting_callback',
            external_task_id='ext-task-1',
        )

    def test_callback_is_idempotent_and_updates_rewrite(self):
        url = reverse('workflow-callback-list')
        payload = {
            'workflow_run_id': str(self.workflow_run.id),
            'node_run_id': str(self.node_run.id),
            'provider': 'linknow',
            'event_type': 'task.completed',
            'idempotency_key': 'callback-1',
            'external_task_id': 'ext-task-1',
            'status': 'completed',
            'payload': {'rewritten_text': '改写结果'},
            'normalized_output': {'rewritten_text': '改写结果'},
            'auto_apply': True,
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WorkflowCallbackEvent.objects.count(), 1)

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WorkflowCallbackEvent.objects.count(), 1)

        self.node_run.refresh_from_db()
        self.assertEqual(self.node_run.status, 'completed')
        rewrite = ContentRewrite.objects.get(project=self.project)
        self.assertEqual(rewrite.rewritten_text, '改写结果')


class WorkflowNodeApplyAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='apply-user', password='secret123')
        self.client.force_authenticate(self.user)
        self.series = Series.objects.create(name='测试作品', description='desc', user=self.user)
        self.project = Project.objects.create(
            user=self.user,
            series=self.series,
            episode_number=1,
            sort_order=1,
            episode_title='第1集',
            name='第1集',
            original_topic='原始文案',
        )
        initialize_project(self.project)
        self.workflow_run = WorkflowRun.objects.create(project=self.project, series=self.series, created_by=self.user)
        self.canvas = WorkflowCanvas.objects.create(
            name='应用画板',
            project=self.project,
            series=self.series,
            created_by=self.user,
            status='active',
        )
        self.storyboard_node_model = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='storyboard_node',
            node_type='storyboard',
            title='分镜',
        )
        self.image_node_model = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='image_node',
            node_type='image_generation',
            title='图片',
        )
        WorkflowEdge.objects.create(
            canvas=self.canvas,
            edge_key='edge-storyboard-image',
            source_node=self.storyboard_node_model,
            target_node=self.image_node_model,
        )

    def test_apply_storyboard_then_images(self):
        storyboard_node = WorkflowNodeRun.objects.create(
            workflow_run=self.workflow_run,
            canvas=self.canvas,
            node=self.storyboard_node_model,
            node_key='storyboard_node',
            node_type='storyboard',
            normalized_output={
                'storyboards': [
                    {
                        'sequence_number': 1,
                        'scene_description': '场景1',
                        'narration_text': '旁白1',
                        'image_prompt': '提示词1',
                        'duration_seconds': 3,
                    }
                ]
            },
        )

        response = self.client.post(reverse('workflow-node-run-apply', args=[storyboard_node.id]), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        storyboard = Storyboard.objects.get(project=self.project, sequence_number=1)
        self.assertEqual(storyboard.scene_description, '场景1')

        image_node = WorkflowNodeRun.objects.create(
            workflow_run=self.workflow_run,
            canvas=self.canvas,
            node=self.image_node_model,
            node_key='image_node',
            node_type='image_generation',
            normalized_output={
                'storyboards': [
                    {
                        'sequence_number': 1,
                        'images': [
                            {
                                'external_task_id': 'img-task-1',
                                'image_url': 'https://example.com/1.png',
                                'status': 'completed',
                                'width': 1280,
                                'height': 720,
                            }
                        ],
                    }
                ]
            },
        )

        response = self.client.post(reverse('workflow-node-run-apply', args=[image_node.id]), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        images = GeneratedImage.objects.filter(storyboard=storyboard)
        self.assertEqual(images.count(), 1)
        self.assertEqual(images.first().image_url, 'https://example.com/1.png')


class WorkflowInvalidationAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='invalidate-user', password='secret123')
        self.client.force_authenticate(self.user)
        self.series = Series.objects.create(name='测试作品', description='desc', user=self.user)
        self.project = Project.objects.create(
            user=self.user,
            series=self.series,
            episode_number=1,
            sort_order=1,
            episode_title='第1集',
            name='第1集',
            original_topic='原始文案',
        )
        initialize_project(self.project)
        self.canvas = WorkflowCanvas.objects.create(
            name='失效画板',
            project=self.project,
            series=self.series,
            created_by=self.user,
            status='active',
        )
        self.node_a = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='node_a',
            node_type='rewrite',
            title='A',
            status='completed',
            config_data={'prompt': 'v1'},
        )
        self.node_b = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='node_b',
            node_type='storyboard',
            title='B',
            status='completed',
        )
        self.node_c = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='node_c',
            node_type='image_generation',
            title='C',
            status='idle',
        )
        WorkflowEdge.objects.create(
            canvas=self.canvas,
            edge_key='edge-a-b',
            source_node=self.node_a,
            target_node=self.node_b,
        )
        WorkflowEdge.objects.create(
            canvas=self.canvas,
            edge_key='edge-b-c',
            source_node=self.node_b,
            target_node=self.node_c,
        )

    def test_graph_update_marks_downstream_nodes_stale_or_dirty(self):
        response = self.client.patch(
            reverse('workflow-canvas-graph', args=[self.canvas.id]),
            {
                'nodes': [
                    {
                        'id': str(self.node_a.id),
                        'canvas': str(self.canvas.id),
                        'node_key': 'node_a',
                        'node_type': 'rewrite',
                        'title': 'A',
                        'status': 'completed',
                        'position_x': 0,
                        'position_y': 0,
                        'width': 320,
                        'height': 180,
                        'config_data': {'prompt': 'v2'},
                        'input_mapping': {},
                        'output_schema': {},
                        'latest_output': {},
                        'is_enabled': True,
                    },
                    {
                        'id': str(self.node_b.id),
                        'canvas': str(self.canvas.id),
                        'node_key': 'node_b',
                        'node_type': 'storyboard',
                        'title': 'B',
                        'status': 'completed',
                        'position_x': 0,
                        'position_y': 0,
                        'width': 320,
                        'height': 180,
                        'config_data': {},
                        'input_mapping': {},
                        'output_schema': {},
                        'latest_output': {},
                        'is_enabled': True,
                    },
                    {
                        'id': str(self.node_c.id),
                        'canvas': str(self.canvas.id),
                        'node_key': 'node_c',
                        'node_type': 'image_generation',
                        'title': 'C',
                        'status': 'idle',
                        'position_x': 0,
                        'position_y': 0,
                        'width': 320,
                        'height': 180,
                        'config_data': {},
                        'input_mapping': {},
                        'output_schema': {},
                        'latest_output': {},
                        'is_enabled': True,
                    },
                ],
                'edges': [
                    {
                        'id': str(self.canvas.edges.get(edge_key='edge-a-b').id),
                        'canvas': str(self.canvas.id),
                        'edge_key': 'edge-a-b',
                        'source_node': str(self.node_a.id),
                        'target_node': str(self.node_b.id),
                        'source_handle': '',
                        'target_handle': '',
                        'metadata': {},
                        'is_enabled': True,
                    },
                    {
                        'id': str(self.canvas.edges.get(edge_key='edge-b-c').id),
                        'canvas': str(self.canvas.id),
                        'edge_key': 'edge-b-c',
                        'source_node': str(self.node_b.id),
                        'target_node': str(self.node_c.id),
                        'source_handle': '',
                        'target_handle': '',
                        'metadata': {},
                        'is_enabled': True,
                    },
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.node_b.refresh_from_db()
        self.node_c.refresh_from_db()
        self.assertEqual(self.node_b.status, 'stale')
        self.assertEqual(self.node_c.status, 'dirty')

    def test_callback_completion_marks_downstream_nodes_stale_or_dirty(self):
        node_run = WorkflowNodeRun.objects.create(
            canvas=self.canvas,
            node=self.node_a,
            node_key='node_a',
            node_type='rewrite',
            status='waiting_callback',
            external_task_id='node-a-task',
        )
        response = self.client.post(
            reverse('workflow-callback-list'),
            {
                'canvas_id': str(self.canvas.id),
                'node_run_id': str(node_run.id),
                'provider': 'linknow',
                'event_type': 'task.completed',
                'idempotency_key': 'node-a-callback',
                'external_task_id': 'node-a-task',
                'status': 'completed',
                'payload': {'rewritten_text': '改写完成'},
                'normalized_output': {'rewritten_text': '改写完成'},
                'auto_apply': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.node_a.refresh_from_db()
        self.node_b.refresh_from_db()
        self.node_c.refresh_from_db()
        self.assertEqual(self.node_a.status, 'completed')
        self.assertEqual(self.node_b.status, 'stale')
        self.assertEqual(self.node_c.status, 'dirty')


class WorkflowNodeExecutionAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='execute-user', password='secret123')
        self.client.force_authenticate(self.user)
        self.series = Series.objects.create(name='测试作品', description='desc', user=self.user)
        self.project = Project.objects.create(
            user=self.user,
            series=self.series,
            episode_number=1,
            sort_order=1,
            episode_title='第1集',
            name='第1集',
            original_topic='原始文案',
        )
        initialize_project(self.project)
        self.canvas = WorkflowCanvas.objects.create(
            name='执行画板',
            project=self.project,
            series=self.series,
            created_by=self.user,
            status='active',
        )
        self.node = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='rewrite_node',
            node_type='rewrite',
            title='改写',
            status='idle',
        )

    @patch('apps.workflows.views.execute_workflow_node_task.delay')
    def test_execute_enqueues_celery_task(self, mock_delay):
        mock_delay.return_value.id = 'celery-node-task-1'

        response = self.client.post(
            reverse('workflow-node-execute', args=[self.node.id]),
            {
                'input_payload': {
                    'original_text': '原文',
                    'instruction': '改成更口语化',
                    'model': 'test-model',
                },
                'trigger_source': 'manual',
                'idempotency_key': 'node-run-1',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'queued')
        self.assertEqual(response.data['external_task_id'], 'celery-node-task-1')
        self.node.refresh_from_db()
        self.assertEqual(self.node.status, 'queued')
        node_run = WorkflowNodeRun.objects.get(id=response.data['id'])
        self.assertEqual(node_run.status, 'queued')
        self.assertEqual(node_run.external_task_id, 'celery-node-task-1')
        mock_delay.assert_called_once_with(str(node_run.id))

    @patch('apps.workflows.views.AsyncResult')
    def test_stream_returns_terminal_event(self, mock_async_result):
        node_run = WorkflowNodeRun.objects.create(
            canvas=self.canvas,
            node=self.node,
            node_key='rewrite_node',
            node_type='rewrite',
            status='completed',
            external_task_id='celery-node-task-2',
            normalized_output={'rewritten_text': '已完成'},
            output_payload={'choices': []},
        )
        mock_async_result.return_value.state = 'SUCCESS'

        response = self.client.get(reverse('workflow-node-run-stream', args=[node_run.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        chunks = list(response.streaming_content)
        payload_text = b''.join(chunks).decode('utf-8')
        self.assertIn('"type": "connected"', payload_text)
        self.assertIn('"type": "done"', payload_text)
        self.assertIn('"status": "completed"', payload_text)

    @patch('apps.workflows.views.AsyncResult')
    def test_stream_accepts_text_event_stream_header(self, mock_async_result):
        node_run = WorkflowNodeRun.objects.create(
            canvas=self.canvas,
            node=self.node,
            node_key='rewrite_node',
            node_type='rewrite',
            status='completed',
            external_task_id='celery-node-task-3',
            normalized_output={'rewritten_text': '已完成'},
        )
        mock_async_result.return_value.state = 'SUCCESS'

        response = self.client.get(
            reverse('workflow-node-run-stream', args=[node_run.id]),
            HTTP_ACCEPT='text/event-stream',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('apps.workflows.views.execute_workflow_node_task.delay')
    def test_execute_selection_enqueues_multiple_nodes(self, mock_delay):
        second_node = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='storyboard_node',
            node_type='storyboard',
            title='分镜',
            status='idle',
        )
        mock_delay.side_effect = [
            SimpleNamespace(id='celery-node-task-11'),
            SimpleNamespace(id='celery-node-task-12'),
        ]

        response = self.client.post(
            reverse('workflow-canvas-execute-selection', args=[self.canvas.id]),
            {
                'nodes': [
                    {
                        'node_id': str(self.node.id),
                        'input_payload': {
                            'original_text': '原文',
                            'instruction': '改成更口语化',
                            'model': 'test-model',
                        },
                        'trigger_source': 'manual',
                        'idempotency_key': 'node-run-batch-1',
                    },
                    {
                        'node_id': str(second_node.id),
                        'input_payload': {
                            'raw_text': '故事文本',
                            'text': '故事文本',
                            'model': 'story-model',
                            'prompt_template_id': 'template-1',
                        },
                        'trigger_source': 'manual',
                        'idempotency_key': 'node-run-batch-2',
                    },
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['summary']['total_count'], 2)
        self.assertEqual(response.data['summary']['queued_count'], 2)
        self.assertEqual(response.data['summary']['failed_count'], 0)
        self.assertEqual(len(response.data['runs']), 2)
        self.assertEqual({item['status'] for item in response.data['runs']}, {'queued'})
        self.assertEqual(mock_delay.call_count, 2)
        self.node.refresh_from_db()
        second_node.refresh_from_db()
        self.assertEqual(self.node.status, 'queued')
        self.assertEqual(second_node.status, 'queued')

    @patch('apps.workflows.views.execute_workflow_node_task.delay')
    def test_execute_selection_rejects_dependent_nodes(self, mock_delay):
        second_node = WorkflowNode.objects.create(
            canvas=self.canvas,
            node_key='image_node',
            node_type='image_generation',
            title='图片',
            status='idle',
        )
        WorkflowEdge.objects.create(
            canvas=self.canvas,
            edge_key='rewrite-to-image',
            source_node=self.node,
            target_node=second_node,
        )

        response = self.client.post(
            reverse('workflow-canvas-execute-selection', args=[self.canvas.id]),
            {
                'nodes': [
                    {
                        'node_id': str(self.node.id),
                        'input_payload': {'original_text': '原文', 'instruction': '改写', 'model': 'test-model'},
                    },
                    {
                        'node_id': str(second_node.id),
                        'input_payload': {'prompt': '补充要求', 'model': 'image-model'},
                    },
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('依赖关系', str(response.data))
        mock_delay.assert_not_called()
