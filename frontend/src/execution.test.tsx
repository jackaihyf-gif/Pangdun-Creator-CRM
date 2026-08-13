import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { CollaborationEditor, ExecutionBoard, ExecutionStatusBar, Workbench } from './main';


const jsonResponse = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('合作执行关键交互', () => {
  it('首次进入时自动落到第一个非空待办分类', async () => {
    const onQueueChange = vi.fn();
    const onQueueResolved = vi.fn();
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith('/api/workbench')) return jsonResponse({
        kpis: {
          today_tasks: 0,
          overdue_tasks: 0,
          upcoming_tasks: 0,
          collaboration_total: 3,
        },
        items: [],
      });
      return jsonResponse({ items: [] });
    }));

    render(<Workbench
      canEdit
      status=""
      search=""
      refreshToken={0}
      queue="today"
      autoResolveQueue
      onQueueResolved={onQueueResolved}
      onQueueChange={onQueueChange}
      onOpen={() => undefined}
    />);

    await waitFor(() => expect(onQueueResolved).toHaveBeenCalledTimes(1));
    expect(onQueueChange).toHaveBeenCalledWith('all');
    expect(screen.getByRole('button', { name: /全部待办/ })).toHaveTextContent('3');
  });

  it('状态轨道与当前筛选值双向同步', async () => {
    const items = [
      { id: 1, execution_status: '待确认' },
      { id: 2, execution_status: '运输中' },
      { id: 3, execution_status: '运输中' },
    ] as any[];
    function StatusHarness() {
      const [value, setValue] = useState('');
      return <><span data-testid="selected-status">{value || '全部'}</span><ExecutionStatusBar items={items} value={value} onChange={setValue} /></>;
    }

    render(<StatusHarness />);
    await userEvent.click(screen.getByRole('tab', { name: /运输中/ }));
    expect(screen.getByTestId('selected-status')).toHaveTextContent('运输中');
    expect(screen.getByRole('tab', { name: /运输中/ })).toHaveAttribute('aria-selected', 'true');

    await userEvent.click(screen.getByRole('tab', { name: /全部/ }));
    expect(screen.getByTestId('selected-status')).toHaveTextContent('全部');
  });

  it('在待办列表中标记缺失的下一步安排', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith('/api/workbench')) return jsonResponse({
        kpis: { collaboration_total: 1 },
        items: [{
          id: 18,
          media_name: 'Missing Plan Creator',
          project_name: 'Launch Project',
          execution_status: '待确认',
          next_action: null,
          follow_up_date: null,
          workflow_health: 'missing_both',
          workflow_label: '待补行动/日期',
        }],
      });
      return jsonResponse({ items: [] });
    }));

    render(<Workbench
      canEdit={false}
      status=""
      search=""
      refreshToken={0}
      queue="all"
      autoResolveQueue={false}
      onQueueResolved={() => undefined}
      onQueueChange={() => undefined}
      onOpen={() => undefined}
    />);

    expect(await screen.findByText('Missing Plan Creator')).toBeInTheDocument();
    expect(screen.getByText('待补行动/日期')).toBeInTheDocument();
  });

  it('登记内容后重新读取详情并刷新内容页签', async () => {
    let contentCreated = false;
    let detailReads = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, options?: RequestInit) => {
      const url = String(input);
      if (url === '/api/collaborations/36') {
        detailReads += 1;
        return jsonResponse({
          id: 36,
          project_id: 7,
          media_id: 9,
          owner_id: 2,
          execution_status: '运输中',
          next_action: '跟踪物流',
          follow_up_date: '2026-08-18',
          follow_up_priority: '普通',
          project: { id: 7, name: 'Launch Project' },
          media: { id: 9, name: 'Creator Test' },
          owner: { id: 2, name: 'Cloris' },
          shipments: [],
          cost_items: [],
          activities: [],
          deliverables: contentCreated ? [{
            id: 88,
            deliverable_type: 'Video Review',
            url: 'https://example.test/review',
            views: 1200,
          }] : [],
        });
      }
      if (url === '/api/deliverables' && options?.method === 'POST') {
        contentCreated = true;
        return jsonResponse({ id: 88 });
      }
      if (url.startsWith('/api/projects')) return jsonResponse({ items: [{ id: 7, name: 'Launch Project' }] });
      if (url.startsWith('/api/media')) return jsonResponse({ items: [{ id: 9, name: 'Creator Test' }] });
      if (url === '/api/users') return jsonResponse({ items: [{ id: 2, name: 'Cloris', email: 'cloris@example.test', role: 'Admin' }] });
      return jsonResponse({ items: [] });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<CollaborationEditor
      value={{ id: 36, project_id: 7, media_id: 9, owner_id: 2, execution_status: '运输中', media: { id: 9, name: 'Creator Test' } } as any}
      onClose={() => undefined}
      onSaved={() => undefined}
    />);

    await screen.findByRole('button', { name: /内容产出/ });
    await userEvent.click(screen.getByRole('button', { name: '3 天后' }));
    const scheduledDate = new Date();
    scheduledDate.setDate(scheduledDate.getDate() + 3);
    const expectedDate = `${scheduledDate.getFullYear()}-${String(scheduledDate.getMonth() + 1).padStart(2, '0')}-${String(scheduledDate.getDate()).padStart(2, '0')}`;
    expect(screen.getByLabelText('跟进日期')).toHaveValue(expectedDate);
    await userEvent.click(screen.getByRole('button', { name: /内容产出/ }));
    expect(await screen.findByText('尚未登记内容产出')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '登记内容' }));
    fireEvent.change(screen.getByLabelText('内容类型'), { target: { value: 'Video Review' } });
    fireEvent.change(screen.getByLabelText('内容链接'), { target: { value: 'https://example.test/review' } });
    const saveButtons = screen.getAllByRole('button', { name: '保存' });
    await userEvent.click(saveButtons[saveButtons.length - 1]);

    await waitFor(() => expect(contentCreated).toBe(true));
    await waitFor(() => expect(detailReads).toBeGreaterThanOrEqual(2));
    expect(await screen.findByText('Video Review')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '查看内容' })).toHaveAttribute('href', 'https://example.test/review');
  });

  it('看板缺少关键资料时才打开补充弹窗', async () => {
    const onChanged = vi.fn();
    const item = {
      id: 42,
      media_id: 9,
      execution_status: '待发货',
      next_status: '运输中',
      advance_ready: false,
      advance_blockers: ['缺少物流单号'],
      advance_requirements: ['tracking_number'],
      media: { id: 9, name: 'Safe Creator' },
      project: { id: 7, name: 'Safe Launch' },
      shipments: [],
    } as any;
    const fetchMock = vi.fn((input: RequestInfo | URL, options?: RequestInit) => {
      const url = String(input);
      if (url === '/api/collaborations/42' && !options?.method) return jsonResponse(item);
      if (url === '/api/collaborations/42/advance' && options?.method === 'POST') return jsonResponse({ ...item, execution_status: '运输中', next_status: '已签收待产出' });
      return jsonResponse({ items: [] });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<ExecutionBoard items={[item]} canEdit onChanged={onChanged} onOpen={() => undefined} />);
    expect(screen.getByText('缺少物流单号')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /确认已发货/ }));
    expect(await screen.findByText('还差这些资料')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('物流单号'), { target: { value: 'TRACK-SAFE-42' } });
    await userEvent.click(screen.getByRole('button', { name: '确认已发货' }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    const advanceCall = fetchMock.mock.calls.find(([url, options]) => String(url) === '/api/collaborations/42/advance' && options?.method === 'POST');
    expect(JSON.parse(String(advanceCall?.[1]?.body))).toMatchObject({ target_status: '运输中', tracking_number: 'TRACK-SAFE-42' });
  });

  it('看板资料齐全时一键推进且不打开弹窗', async () => {
    const onChanged = vi.fn();
    const item = {
      id: 43,
      media_id: 10,
      execution_status: '待确认',
      next_status: '待发货',
      advance_ready: true,
      advance_blockers: [],
      advance_requirements: [],
      media: { id: 10, name: 'Quick Creator' },
      project: { id: 8, name: 'Quick Launch' },
      shipments: [],
    } as any;
    const fetchMock = vi.fn((input: RequestInfo | URL, options?: RequestInit) => {
      const url = String(input);
      if (url === '/api/collaborations/43' && !options?.method) return jsonResponse(item);
      if (url === '/api/collaborations/43/advance' && options?.method === 'POST') return jsonResponse({ ...item, execution_status: '待发货', next_status: '运输中' });
      return jsonResponse({ items: [] });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<ExecutionBoard items={[item]} canEdit onChanged={onChanged} onOpen={() => undefined} />);
    await userEvent.click(screen.getByRole('button', { name: /进入待发货/ }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('补充资料')).not.toBeInTheDocument();
    const advanceCall = fetchMock.mock.calls.find(([url, options]) => String(url) === '/api/collaborations/43/advance' && options?.method === 'POST');
    expect(JSON.parse(String(advanceCall?.[1]?.body))).toEqual({ target_status: '待发货' });
  });
});
