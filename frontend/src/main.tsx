import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Button, Card, ConfirmHost, Dialog, Input, Notification, Popover, Select, Table, Tag, Title, Toaster, confirmAction } from './components/ui';
import { Archive, ArrowRight, Bot, Boxes, CalendarDays, CheckCircle2, ClipboardList, Copy, Download, FileSpreadsheet, Filter, GitMerge, LayoutDashboard, Link2, LogOut, Megaphone, MoreHorizontal, Package, Pencil, Plus, RefreshCw, Search, ShieldCheck, Sparkles, Trash2, Truck, UploadCloud, UserCog, UserPlus, Users, Wallet } from 'lucide-react';
import './styles.css';
import './glass.css';
import './crm-warm.css';

type View = 'workbench' | 'projects' | 'archive' | 'agent' | 'media' | 'products' | 'import' | 'users';
type User = { id: number; email: string; name: string; role: 'Admin' | 'Editor' | 'Viewer'; is_active?: boolean; created_at?: string };
type ProfileLink = { platform: string; url: string; followers_k?: number | null; source?: string; confidence?: number | null; verified_at?: string };
type Media = { id: number; name: string; country?: string; country_code?: string; region?: string; category?: string; platform_type?: string; website_url?: string; profile_links?: ProfileLink[]; followers_or_traffic?: number | null; audience_metric_type?: string; audience_metric_unit?: string; metric_source?: string; metric_verified_at?: string; data_source?: string; data_capture_method?: string; data_confidence?: number | null; last_verified_at?: string; review_snoozed_until?: string; media_tier?: string | null; cooperation_status?: string; verification_status?: string; notes?: string };
type ShippingAddress = { id: number; media_id: number; contact_id?: number | null; recipient_name?: string; phone?: string; email?: string; address_text: string; city?: string; region?: string; postal_code?: string; country?: string; tax_or_customs_number?: string; shipping_notes?: string; source_text?: string; is_default: boolean; is_confirmed: boolean };
type AgentRun = { id: number; input_type: string; source_label?: string; status: string; model?: string; proposal?: any; usage?: any; error_message?: string; target_media_id?: number | null; user?: string; reviewed_by?: string; created_at: string; reviewed_at?: string };
type Project = { id: number; name: string; project_code?: string; owner_id?: number; status: string; budget_amount?: number; budget_currency?: string; collaboration_tag?: string; actual_amount?: number; campaign_count?: number; owner?: User; objective?: string; notes?: string; start_date?: string; end_date?: string; is_archived?: boolean; archived_at?: string };
type WorkflowHealth = 'ready' | 'overdue' | 'missing_action' | 'missing_date' | 'missing_both' | 'needs_next_step' | 'closed';
type Collaboration = { id: number; project_id?: number; media_id: number; owner_id?: number; collaboration_type?: string; execution_status: string; execution_status_changed_at?: string; days_in_status?: number; expected_publish_date?: string; next_action?: string; follow_up_date?: string; follow_up_priority?: string; follow_up_done?: boolean; workflow_health?: WorkflowHealth; workflow_label?: string; workflow_warnings?: string[]; next_status?: string | null; advance_ready?: boolean; advance_blockers?: string[]; advance_requirements?: string[]; notes?: string; project?: Project; media?: Media; owner?: User; shipments?: any[]; cost_items?: any[]; deliverables?: any[]; activities?: any[] };

const statusOptions = ['待确认', '待发货', '运输中', '已签收待产出', '内容审核中', '已发布', '已结算', '已暂停', '已取消'];
const shipmentStatusOptions = ['待发货', '运输中', '已签收待产出'];
const mediaChannelOptions = ['YouTube', 'Instagram', 'TikTok', 'X', 'Bilibili', '多平台', '科技媒体 / 网站', '其他'];
const mediaTierOptions = ['S', 'A', 'B', 'C', 'D', '待评估'];
const cooperationStatusOptions = ['未联系', '待回复', '洽谈中', '已合作', '暂缓', '不合作'];
const nextActionByStatus: Record<string, string> = { '待确认': '确认合作意向与报价', '待发货': '确认收件信息并安排寄样', '运输中': '跟踪物流并同步预计到达时间', '已签收待产出': '确认内容排期与脚本方向', '内容审核中': '完成内容审核并反馈修改意见', '已发布': '回收内容链接与效果数据', '已结算': '归档合作结果与复盘', '已暂停': '确认恢复条件与下一次检查时间', '已取消': '归档取消原因与合作结论', '已暂停/取消': '确认恢复条件与下一次检查时间' };
const workflowStatuses = statusOptions.filter((item) => !['已暂停', '已取消'].includes(item));
const followUpClosedStatuses = new Set(['已结算', '已暂停', '已取消', '已暂停/取消']);
const advanceActionLabel: Record<string, string> = { '待发货': '进入待发货', '运输中': '确认已发货', '已签收待产出': '确认已签收', '内容审核中': '提交内容审核', '已发布': '确认已发布', '已结算': '确认已结算' };
const formatDateTime = (value?: string) => value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
const performanceSample = (item: any, kind: string) => item.performance_snapshots?.find((sample: any) => sample.sample_kind === kind);
const monitoringLabel = (status?: string) => ({ waiting_day_1: '等待首日数据', waiting_day_3: '等待三日数据', completed: '三日采集完成', late_discovered: '发布三日后发现' } as Record<string, string>)[status || ''] || '人工登记';
const inputDateAfter = (days: number) => { const value = new Date(); value.setDate(value.getDate() + days); return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`; };
const copyValue = async (value: string, label: string) => { try { await navigator.clipboard.writeText(value); Notification.success({ message: `${label}已复制` }); } catch { Notification.error({ message: '复制失败，请手动选择文本' }); } };

function workflowHealthOf(item: Partial<Collaboration>): { code: WorkflowHealth; label: string; warnings: string[] } {
  if (followUpClosedStatuses.has(item.execution_status || '')) return { code: 'closed', label: '无需跟进', warnings: [] };
  if (item.follow_up_done) return { code: 'needs_next_step', label: '待续排', warnings: ['当前待办已完成，请安排新的下一步行动和日期'] };
  const missingAction = !item.next_action?.trim();
  const missingDate = !item.follow_up_date;
  if (missingAction && missingDate) return { code: 'missing_both', label: '待补行动/日期', warnings: ['缺少下一步行动', '缺少跟进日期'] };
  if (missingAction) return { code: 'missing_action', label: '待补行动', warnings: ['缺少下一步行动'] };
  if (missingDate) return { code: 'missing_date', label: '待排期', warnings: ['缺少跟进日期'] };
  if (!item.follow_up_done && item.follow_up_date! < inputDateAfter(0)) return { code: 'overdue', label: '已逾期', warnings: ['跟进日期已逾期'] };
  return { code: 'ready', label: '已安排', warnings: [] };
}

async function advanceWithGuard(item: Collaboration, onAdvanced: (result: Collaboration) => void, onNeedsInput: (detail: Collaboration) => void) {
  try {
    const detail = await api<Collaboration>(`/api/collaborations/${item.id}`);
    if (!detail.next_status) return Notification.warning({ message: '当前合作已完成执行流程' });
    if (!detail.advance_ready) return onNeedsInput(detail);
    const result = await api<Collaboration>(`/api/collaborations/${item.id}/advance`, { method: 'POST', body: JSON.stringify({ target_status: detail.next_status }) });
    onAdvanced(result);
    Notification.success({
      message: `已${advanceActionLabel[detail.next_status] || `推进到${detail.next_status}`}`,
      description: '阶段变化已自动记录',
      duration: 30000,
      action: {
        label: '撤销',
        onClick: () => void api<Collaboration>(`/api/collaborations/${item.id}/undo-advance`, { method: 'POST' }).then((undone) => { onAdvanced(undone); Notification.success({ message: `已撤销，恢复到“${undone.execution_status}”` }); }).catch((error) => Notification.error({ message: '撤销失败', description: String(error) })),
      },
    });
  } catch (error) {
    Notification.error({ message: '暂时无法推进', description: String(error) });
  }
}

function WorkflowHealthBadge({ item }: { item: Partial<Collaboration> }) {
  const health = item.workflow_health ? { code: item.workflow_health, label: item.workflow_label || workflowHealthOf(item).label } : workflowHealthOf(item);
  if (health.code === 'ready' || health.code === 'closed') return null;
  return <span className={`workflow-health workflow-health-${health.code}`}>{health.label}</span>;
}

export function ExecutionStatusBar({ items, value, onChange }: { items: Collaboration[]; value: string; onChange: (value: string) => void }) {
  const countOf = (status: string) => items.filter((item) => item.execution_status === status).length;
  return <div className="execution-status-bar" role="tablist" aria-label="按合作状态筛选"><button type="button" role="tab" aria-selected={!value} className={`status-all ${!value ? 'active' : ''}`} onClick={() => onChange('')}><span>全部</span><em>{items.length}</em></button><i className="status-divider" aria-hidden="true" /><div className="status-flow">{statusOptions.map((status, index) => <button type="button" role="tab" aria-selected={value === status} className={`${value === status ? 'active' : ''}${['已暂停', '已取消'].includes(status) ? ' status-muted' : ''}`} key={status} onClick={() => onChange(status)}><b aria-hidden="true" /><span>{status}</span><em>{countOf(status)}</em>{index < statusOptions.length - 1 && <i aria-hidden="true" />}</button>)}</div></div>;
}

function ShipmentQuickInfo({ row }: { row: Collaboration }) {
  const shipments = row.shipments || [];
  const oa = [...new Set(shipments.map((item: any) => item.oa_pi_number).filter(Boolean))].join('、');
  const tracking = [...new Set(shipments.map((item: any) => item.tracking_number).filter(Boolean))].join('、');
  return <div className="shipment-quick-info"><div><span>OA / PI</span>{oa ? <><strong title={oa}>{oa}</strong><button type="button" title="复制 OA / PI" onClick={() => void copyValue(oa, 'OA / PI')}><Copy size={13} /></button></> : <em>—</em>}</div><div><span>物流</span>{tracking ? <><strong title={tracking}>{tracking}</strong><button type="button" title="复制物流单号" onClick={() => void copyValue(tracking, '物流单号')}><Copy size={13} /></button></> : <em>—</em>}</div></div>;
}

async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { credentials: 'include', headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' }, ...options });
  if (!response.ok) throw new Error((await response.text()) || response.statusText);
  return response.json();
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<View>('workbench');
  const [loading, setLoading] = useState(true);
  useEffect(() => { api<User>('/api/auth/me').then(setUser).catch(() => setUser(null)).finally(() => setLoading(false)); }, []);
  if (loading) return <div className="splash"><img src="/assets/pangdun/pangdun_walk.gif" alt="Pangdun" /></div>;
  if (!user) return <Login onLogin={setUser} />;
  return <Shell user={user} view={view} setView={setView} onLogout={() => setUser(null)} />;
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState('admin@example.local');
  const [password, setPassword] = useState('admin123456');
  return <main className="login-page"><section className="login-panel"><div className="login-visual"><img src="/assets/pangdun/pangdun_happy.png" alt="Pangdun" /></div><form className="login-form" onSubmit={async (e) => { e.preventDefault(); try { onLogin(await api<User>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })); } catch { Notification.error({ message: '登录失败' }); } }}><div className="login-heading"><span className="eyebrow">PANGDUN WORKSPACE</span><Title size="large">Pangdun KOL CRM</Title><p>管理媒体、合作、寄样与内容产出</p></div><label>邮箱<Input autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>密码<Input autoComplete="current-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label><Button type="primary" htmlType="submit" block>登录</Button></form></section></main>;
}

function Shell({ user, view, setView, onLogout }: { user: User; view: View; setView: (view: View) => void; onLogout: () => void }) {
  const workspaceNav: Array<[View, string, React.ReactNode]> = [['workbench', '合作执行', <LayoutDashboard size={18} strokeWidth={1.75} />], ['projects', '项目管理', <Megaphone size={18} strokeWidth={1.75} />], ['archive', '历史归档', <Archive size={18} strokeWidth={1.75} />], ['agent', '胖墩 Agent', <Bot size={18} strokeWidth={1.75} />]];
  const resourceNav: Array<[View, string, React.ReactNode]> = [['media', '媒体 / KOL', <Users size={18} strokeWidth={1.75} />], ['products', '产品库', <Boxes size={18} strokeWidth={1.75} />], ['import', '统一导入', <FileSpreadsheet size={18} strokeWidth={1.75} />], ...(user.role === 'Admin' ? [['users', '用户管理', <UserCog size={18} strokeWidth={1.75} />] as [View, string, React.ReactNode]] : [])];
  const renderNav = (items: Array<[View, string, React.ReactNode]>) => items.map(([key, label, icon]) => <button key={key} className={view === key ? 'active' : ''} onClick={() => { setView(key); window.scrollTo({ top: 0 }); }}>{icon}<span>{label}</span></button>);
  const logout = async () => { await api('/api/auth/logout', { method: 'POST' }); onLogout(); };
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><img src="/assets/pangdun/pangdun.png" alt="Pangdun" /><div><strong>Pangdun CRM</strong><span>KOL Collaboration OS</span></div></div><nav><div className="nav-group"><span className="nav-label">应用中心</span>{renderNav(workspaceNav)}</div><div className="nav-group"><span className="nav-label">资源与数据</span>{renderNav(resourceNav)}</div></nav><button className="logout" onClick={logout}><LogOut size={18} />退出登录</button></aside><main className="content"><header className="account-bar"><div className="account-button"><span className="account-avatar">{user.name.slice(0, 1).toUpperCase()}</span><strong>{user.name}</strong></div></header><div className="page-stage">{view === 'workbench' && <Execution canEdit={user.role !== 'Viewer'} canManage={user.role === 'Admin'} />}{view === 'projects' && <Projects canEdit={user.role !== 'Viewer'} canManage={user.role === 'Admin'} />}{view === 'archive' && <ArchiveManager canManage={user.role === 'Admin'} />}{view === 'agent' && <AgentWorkspace canEdit={user.role !== 'Viewer'} canManage={user.role === 'Admin'} />}{view === 'media' && <Library type="media" canEdit={user.role !== 'Viewer'} canManage={user.role === 'Admin'} />}{view === 'products' && <Library type="products" canEdit={user.role !== 'Viewer'} canManage={user.role === 'Admin'} />}{view === 'import' && <ExecutionImport />}{view === 'users' && <UsersPage />}</div></main></div>;
}

function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) { return <header className="page-header"><div><Title color="app-teal">{title}</Title>{subtitle && <p>{subtitle}</p>}</div>{action}</header>; }
function Empty() { return <div className="empty"><img src="/assets/pangdun/pangdun_think.png" alt="" /><span>还没有记录</span></div>; }
function SelectAllHeader() { const [checked, setChecked] = useState(false); return <input type="checkbox" aria-label="全选当前列表" checked={checked} onChange={(event) => { setChecked(event.target.checked); window.dispatchEvent(new CustomEvent('workbench-select-all', { detail: event.target.checked })); }} />; }
function DataTable({ columns, data }: { columns: any[]; data: any[] }) { const normalized = columns.map((column, index) => index === 0 && column.title === '' ? { ...column, title: <SelectAllHeader /> } : column); const minWidth = normalized.reduce((total, column) => total + (column.width || 140), 0); return <div className="table-wrap"><Table columns={normalized} dataSource={data} rowKey="id" scroll={{ x: minWidth }} emptyText={<Empty />} /></div>; }
function SelectField({ value, onChange, options, placeholder = '请选择' }: { value?: string | number; onChange: (v: string) => void; options: Array<{ key: string; label: string }>; placeholder?: string }) { return <Select value={value} onChange={onChange} options={options.map((option) => ({ value: option.key, label: option.label }))} placeholder={placeholder} />; }

type LookupOption = { id: number; label: string; search?: string };
function EntityLookup({ value, options, onChange, placeholder = '输入关键词搜索' }: { value?: number | null; options: LookupOption[]; onChange: (id: number | null) => void; placeholder?: string }) {
  const selected = options.find((option) => option.id === value);
  const [query, setQuery] = useState(selected?.label || '');
  const [focused, setFocused] = useState(false);
  useEffect(() => { setQuery(selected?.label || ''); }, [value, selected?.label]);
  const normalized = query.trim().toLowerCase();
  const matches = options.filter((option) => !normalized || `${option.label} ${option.search || ''}`.toLowerCase().includes(normalized)).slice(0, 8);
  return <div className="lookup-control"><div className="lookup-input-row"><input value={query} placeholder={placeholder} autoComplete="off" onFocus={() => setFocused(true)} onBlur={() => window.setTimeout(() => setFocused(false), 120)} onChange={(event) => { setQuery(event.target.value); onChange(null); }} />{value != null && <button type="button" className="lookup-clear" title="清除选择" onClick={() => { setQuery(''); onChange(null); }}>×</button>}</div>{focused && <div className="lookup-results">{matches.length ? matches.map((option) => <button type="button" key={option.id} onMouseDown={(event) => { event.preventDefault(); setQuery(option.label); onChange(option.id); setFocused(false); }}>{option.label}</button>) : <span>没有匹配结果</span>}</div>}</div>;
}

const mediaLookupOptions = (media: Media[]): LookupOption[] => media.map((item) => ({ id: item.id, label: `${item.name}${item.country ? ` · ${item.country}` : ''}${item.platform_type ? ` · ${item.platform_type}` : ''}`, search: `${item.name} ${item.country || ''} ${item.platform_type || ''} ${item.website_url || ''}` }));
const projectLookupOptions = (projects: Project[]): LookupOption[] => projects.map((item) => ({ id: item.id, label: `${item.name}${item.project_code ? ` · ${item.project_code}` : ''}`, search: `${item.name} ${item.project_code || ''} ${item.objective || ''}` }));
const campaignLookupOptions = (campaigns: Collaboration[]): LookupOption[] => campaigns.map((item) => ({ id: item.id, label: `${item.media?.name || `执行单 ${item.id}`}${item.media?.country ? ` · ${item.media.country}` : ''}`, search: `${item.media?.name || ''} ${item.media?.country || ''} ${item.project?.name || ''} ${item.execution_status || ''}` }));

export function Workbench({ canEdit, status, search, refreshToken, queue, autoResolveQueue, onQueueResolved, onQueueChange, onOpen }: { canEdit: boolean; status: string; search: string; refreshToken: number; queue: string; autoResolveQueue: boolean; onQueueResolved: () => void; onQueueChange: (queue: string) => void; onOpen: (id: number) => void }) {
  const [data, setData] = useState<any>({ kpis: {}, items: [] });
  const [paymentPending] = useState(false);
  const initialQueueResolved = useRef(false);
  const [projects, setProjects] = useState<Project[]>([]); const [media, setMedia] = useState<Media[]>([]); const [users, setUsers] = useState<User[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set()); const [bulk, setBulk] = useState<any>(null); const [bulkPreview, setBulkPreview] = useState<any>(null);
  const load = (nextStatus = status, nextPaymentPending = paymentPending, nextQueue = queue) => { const params = new URLSearchParams({ queue: nextQueue }); if (nextStatus) params.set('execution_status', nextStatus); if (nextPaymentPending) params.set('payment_pending', 'true'); return api<any>(`/api/workbench?${params}`).then((result) => { setData(result); setSelected(new Set()); if (autoResolveQueue && !initialQueueResolved.current) { initialQueueResolved.current = true; onQueueResolved(); const nextAvailable = ([['today', result.kpis.today_tasks], ['overdue', result.kpis.overdue_tasks], ['upcoming', result.kpis.upcoming_tasks], ['all', result.kpis.collaboration_total]] as Array<[string, number]>).find(([, count]) => Number(count || 0) > 0)?.[0]; if (nextAvailable && nextAvailable !== nextQueue) onQueueChange(nextAvailable); } }).catch(() => Notification.error({ message: '读取执行数据失败' })); };
  useEffect(() => { void load(); }, [queue, status, refreshToken]);
  useEffect(() => { api<{ items: Project[] }>('/api/projects?page_size=300').then((x) => setProjects(x.items)); api<{ items: Media[] }>('/api/media?page_size=500').then((x) => setMedia(x.items)); api<{ items: User[] }>('/api/users').then((x) => setUsers(x.items)).catch(() => {}); }, []);
  const patch = async (id: number, value: any) => { try { await api(`/api/collaborations/${id}`, { method: 'PATCH', body: JSON.stringify(value) }); await load(); } catch (error) { Notification.error({ message: '保存失败', description: String(error) }); } };
  const applyBulk = async (confirm = false) => { if (!bulk || !selected.size) return; try { const payload: any = { ids: [...selected], preview: !confirm }; if (bulk.owner_id) payload.owner_id = Number(bulk.owner_id); if (bulk.follow_up_date) payload.follow_up_date = bulk.follow_up_date; if (bulk.follow_up_priority) payload.follow_up_priority = bulk.follow_up_priority; const result = await api<any>('/api/collaborations/bulk', { method: 'PATCH', body: JSON.stringify(payload) }); if (!confirm) { setBulkPreview(result); return; } setBulkPreview(null); setBulk(null); await load(); Notification.success({ message: `已更新 ${result.updated} 条执行单` }); } catch (error) { Notification.error({ message: '批量更新失败', description: String(error) }); } };
  useEffect(() => { const selectAll = (event: Event) => { const checked = (event as CustomEvent<boolean>).detail; setSelected(checked ? new Set(data.items.map((item: any) => item.id)) : new Set()); }; window.addEventListener('workbench-select-all', selectAll); return () => window.removeEventListener('workbench-select-all', selectAll); }, [data.items]);
  const toggle = (id: number) => setSelected((previous) => { const next = new Set(previous); next.has(id) ? next.delete(id) : next.add(id); return next; });
  const visibleItems = data.items.filter((item: any) => !search.trim() || [item.media_name, item.project_name, item.next_action, item.owner, item.platform_type, item.country].some((value) => String(value || '').toLowerCase().includes(search.trim().toLowerCase())));
  const queueCounts: Record<string, number> = { overdue: data.kpis.overdue_tasks || 0, today: data.kpis.today_tasks || 0, upcoming: data.kpis.upcoming_tasks || 0, all: data.kpis.collaboration_total || 0 };
  return <section className="workbench-page"><div className="queue-tabs">{[['today', '今天'], ['overdue', '逾期跟进'], ['upcoming', '未来 7 天'], ['all', '全部待办']].map(([key, label]) => <button key={key} className={queue === key ? 'active' : ''} onClick={() => { initialQueueResolved.current = true; onQueueChange(key); }}><span>{label}</span><em>{queueCounts[key] || 0}</em></button>)}</div><div className="workbench-metrics"><span><Package size={14} />待发货 <strong>{data.kpis.pending_shipping || 0}</strong></span><span><Truck size={14} />运输中 <strong>{data.kpis.in_transit || 0}</strong></span><span><ClipboardList size={14} />待产出 <strong>{data.kpis.awaiting_content || 0}</strong></span><span><Wallet size={14} />待付款 <strong>{data.kpis.pending_payment || 0}</strong></span><span className="summary-money">费用实付 ¥{Number(data.kpis.actual_amount || 0).toLocaleString()}</span></div><div className="workbench-list-heading"><div><strong>{queue === 'overdue' ? '逾期跟进' : queue === 'today' ? '今日跟进' : queue === 'upcoming' ? '未来 7 天' : '全部待办'} · {visibleItems.length}</strong><span>按下一步日期排序，直接在表格内更新字段</span></div>{canEdit && selected.size > 0 && <Button onClick={() => setBulk({})}>批量更新 · {selected.size}</Button>}</div><DataTable data={visibleItems} columns={[{ title: '', render: (_: any, r: any) => canEdit ? <input type="checkbox" checked={selected.has(r.id)} onChange={() => toggle(r.id)} /> : null, width: 44 }, { title: '合作对象', render: (_: any, r: any) => <button type="button" className="entity-open-button" onClick={() => onOpen(r.id)}><WorkbenchEntity name={r.media_name} platform={r.platform_type} country={r.country} /></button>, width: 170 }, { title: '合作项目', render: (_: any, r: any) => <InlineLookup value={r.project_name} options={projects.map((x) => ({ id: x.id, label: `${x.name}${x.project_code ? ` · ${x.project_code}` : ''}` }))} onSave={(id) => patch(r.id, { project_id: id })} />, width: 140 }, { title: '下一步行动', render: (_: any, r: any) => <div className="next-action-stack"><div className="next-action-cell"><CheckCircle2 size={15} /><InlineText value={r.next_action || ''} onSave={(value) => patch(r.id, { next_action: value || null, follow_up_done: false })} /></div><WorkflowHealthBadge item={r} /></div>, width: 190 }, { title: '下一步时间', render: (_: any, r: any) => <div className="date-cell"><CalendarDays size={14} /><InlineText type="date" value={r.follow_up_date || ''} onSave={(value) => patch(r.id, { follow_up_date: value || null, follow_up_done: false })} /></div>, width: 125 }, { title: '状态', render: (_: any, r: any) => <div><StatusTag value={r.execution_status} />{r.days_in_status != null && <small className="stage-age">{r.days_in_status} 天</small>}</div>, width: 115 }, { title: '负责人', render: (_: any, r: any) => <div className="owner-cell"><span>{String(r.owner || '?').slice(0, 1)}</span><InlineSelect value={r.owner} options={users.map((x) => ({ value: String(x.id), label: x.name }))} onSave={(value) => patch(r.id, { owner_id: value ? Number(value) : null })} /></div>, width: 100 }, { title: '', render: (_: any, r: any) => canEdit && <button className="task-done" title="完成待办" onClick={() => patch(r.id, { follow_up_done: true })}><CheckCircle2 size={17} /></button>, width: 54 }]} />{bulk && <Dialog variant="modal" title={`批量更新 ${selected.size} 条执行单`} onClose={() => { setBulk(null); setBulkPreview(null); }} onOk={() => void applyBulk()} okLabel="预览变更"><div className="form-grid"><label>负责人<SelectField value={bulk.owner_id} onChange={(owner_id) => setBulk({ ...bulk, owner_id })} options={users.map((x) => ({ key: String(x.id), label: x.name }))} /></label><label>跟进日期<Input type="date" value={bulk.follow_up_date || ''} onChange={(e) => setBulk({ ...bulk, follow_up_date: e.target.value })} /></label><label>优先级<SelectField value={bulk.follow_up_priority} onChange={(follow_up_priority) => setBulk({ ...bulk, follow_up_priority })} options={['高', '普通', '低'].map((x) => ({ key: x, label: x }))} /></label></div></Dialog>}{bulkPreview && <Dialog variant="modal" title={`确认批量更新 · ${bulkPreview.matched} 条`} onClose={() => setBulkPreview(null)} onOk={() => void applyBulk(true)} okLabel="确认写入"><div className="bulk-preview-list">{bulkPreview.items?.map((item: any) => <article key={item.id}><strong>{item.media || `执行单 ${item.id}`}</strong><span>{Object.keys(item.after || {}).map((key) => `${key}: ${item.before?.[key] || '空'} → ${item.after?.[key] || '空'}`).join('；')}</span></article>)}</div></Dialog>}</section>;
}

function WorkbenchEntity({ name, platform, country }: { name?: string; platform?: string; country?: string }) { const label = name || '未命名合作对象'; return <div className="entity-cell"><span className="entity-avatar">{label.slice(0, 1).toUpperCase()}</span><span><strong>{label}</strong><small>{[platform, country].filter(Boolean).join(' · ') || '档案待完善'}</small></span></div>; }

function InlineText({ value, onSave, type = 'text' }: { value: string; onSave: (value: string) => void; type?: string }) { const [editing, setEditing] = useState(false); const [draft, setDraft] = useState(value); useEffect(() => setDraft(value), [value]); if (!editing) return <button className="inline-cell" onClick={() => setEditing(true)}>{value || '—'}</button>; return <input className="inline-input" autoFocus type={type} value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={() => { setEditing(false); if (draft !== value) onSave(draft); }} onKeyDown={(e) => { if (e.key === 'Escape') { setDraft(value); setEditing(false); } if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur(); }} />; }
function InlineSelect({ value, options, onSave }: { value?: string; options: Array<{ value: string; label: string }>; onSave: (value: string) => void }) { const selectedValue = options.find((option) => option.label === value)?.value || value || ''; return <Select compact className="inline-select-control" value={selectedValue} options={options} placeholder="未分配" onChange={onSave} />; }
function InlineLookup({ value, options, onSave }: { value?: string; options: Array<{ id: number; label: string }>; onSave: (id: number | null) => void }) { const [editing, setEditing] = useState(false); const [draft, setDraft] = useState(value || ''); const listId = `lookup-${Math.random().toString(36).slice(2)}`; if (!editing) return <button className="inline-cell" onClick={() => { setDraft(value || ''); setEditing(true); }}>{value || '未归属'}</button>; const save = () => { const matched = options.find((x) => x.label === draft) || options.find((x) => x.label.toLowerCase().includes(draft.toLowerCase())); setEditing(false); if (matched) onSave(matched.id); else setDraft(value || ''); }; return <><input className="inline-input" autoFocus list={listId} value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={save} onKeyDown={(e) => { if (e.key === 'Escape') { setDraft(value || ''); setEditing(false); } if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur(); }} /><datalist id={listId}>{options.map((x) => <option key={x.id} value={x.label} />)}</datalist></>; }

function StatusTag({ value }: { value: string }) { const tone = ['已取消'].includes(value) ? 'status-tag-cancelled' : ['已暂停', '已暂停/取消'].includes(value) ? 'status-tag-paused' : ''; return <Tag className={tone}>{value}</Tag>; }
function KpiHit({ label, icon, onClick }: { label: string; icon: React.ReactNode; onClick: () => void }) { return <>{icon}<button type="button" className="kpi-hit-area" aria-label={`查看${label}执行单`} title={`查看${label}执行单`} onClick={onClick} /></>; }

function Projects({ canEdit, canManage }: { canEdit: boolean; canManage: boolean }) {
  const [items, setItems] = useState<Project[]>([]); const [users, setUsers] = useState<User[]>([]); const [editing, setEditing] = useState<Partial<Project> | null>(null); const [selected, setSelected] = useState<number | null>(null); const [statusFilter, setStatusFilter] = useState(''); const [ownerFilter, setOwnerFilter] = useState(''); const [query, setQuery] = useState('');
  const load = () => api<{ items: Project[] }>('/api/projects?page_size=300').then((x) => setItems(x.items)); useEffect(() => { void load(); api<{ items: User[] }>('/api/users').then((x) => setUsers(x.items)).catch(() => {}); }, []);
  if (selected) return <ProjectDetail id={selected} onBack={() => { setSelected(null); load(); }} canEdit={canEdit} canManage={canManage} />;
  const save = async () => { if (!editing?.name?.trim()) return Notification.error({ message: '请填写项目名称' }); try { await api(editing.id ? `/api/projects/${editing.id}` : '/api/projects', { method: editing.id ? 'PUT' : 'POST', body: JSON.stringify({ ...editing, name: editing.name.trim() }) }); setEditing(null); await load(); Notification.success({ message: editing.id ? '项目信息已更新' : '项目已创建' }); } catch (e) { Notification.error({ message: '保存失败', description: String(e) }); } };
  const newProject = () => setEditing({ name: '', project_code: '', owner_id: undefined, objective: '', notes: '', start_date: undefined, end_date: undefined, status: 'Active', budget_currency: 'CNY', budget_amount: undefined });
  const archiveProject = async () => { if (!editing?.id || !await confirmAction(`确定归档项目“${editing.name}”吗？\n\n归档后项目及其执行单会从日常列表、工作台和 KPI 中隐藏，可在“历史归档”恢复。`)) return; try { await api(`/api/projects/${editing.id}/archive`, { method: 'POST' }); setEditing(null); await load(); Notification.success({ message: '项目已归档' }); } catch (error) { Notification.error({ message: '归档失败', description: String(error) }); } };
  const deleteProject = async () => { if (!editing?.id) return; try { const detail = await api<any>(`/api/projects/${editing.id}`); const rows = detail.campaigns || []; const shipments = rows.reduce((sum: number, row: any) => sum + (row.shipments?.length || 0), 0); const costs = rows.reduce((sum: number, row: any) => sum + (row.cost_items?.length || 0), 0); const content = rows.reduce((sum: number, row: any) => sum + (row.deliverables?.length || 0), 0); const activities = rows.reduce((sum: number, row: any) => sum + (row.activities?.length || 0), 0); if (!await confirmAction(`永久删除项目“${editing.name}”？\n\n将删除 ${rows.length} 条执行单、${shipments} 条寄样、${costs} 条费用、${content} 条内容和 ${activities} 条动态。媒体、联系人和产品不会删除。此操作不可撤销。`)) return; await api(`/api/projects/${editing.id}`, { method: 'DELETE' }); setEditing(null); await load(); Notification.success({ message: '项目已永久删除' }); } catch (error) { Notification.error({ message: '删除失败', description: String(error) }); } };
  const visibleItems = items.filter((item) => (!statusFilter || item.status === statusFilter) && (!ownerFilter || String(item.owner_id || item.owner?.id || '') === ownerFilter) && (!query.trim() || `${item.name} ${item.project_code || ''}`.toLowerCase().includes(query.trim().toLowerCase())));
  const budgetTotal = items.reduce((sum, item) => sum + Number(item.budget_amount || 0), 0); const actualTotal = items.reduce((sum, item) => sum + Number(item.actual_amount || 0), 0); const campaignsTotal = items.reduce((sum, item) => sum + Number(item.campaign_count || 0), 0);
  const statusLabel: Record<string, string> = { Active: '进行中', Paused: '已暂停', Completed: '已完成' };
  return <section className="resource-page"><PageHeader title="项目管理" subtitle="从项目维度查看合作进度、负责人和预算使用情况" action={canEdit && <Button type="primary" icon={<Plus size={16} />} onClick={newProject}>新建项目</Button>} /><div className="resource-summary-grid"><div><span>进行中项目</span><strong>{items.filter((item) => item.status === 'Active').length}</strong></div><div><span>合作执行单</span><strong>{campaignsTotal}</strong></div><div><span>预算使用</span><strong>{budgetTotal ? `${Math.round(actualTotal / budgetTotal * 100)}%` : '—'}</strong><small>{budgetTotal ? `¥${actualTotal.toLocaleString()} / ¥${budgetTotal.toLocaleString()}` : '尚未录入预算'}</small></div></div><div className="resource-toolbar"><div className="resource-tabs" role="tablist">{[{ key: '', label: '全部' }, { key: 'Active', label: '进行中' }, { key: 'Paused', label: '已暂停' }, { key: 'Completed', label: '已完成' }].map((option) => <button key={option.key} type="button" className={statusFilter === option.key ? 'active' : ''} onClick={() => setStatusFilter(option.key)}>{option.label}<span>{option.key ? items.filter((item) => item.status === option.key).length : items.length}</span></button>)}</div><div className="resource-filters"><label className="resource-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目名称或 OA / PI" /></label><Select compact ariaLabel="按负责人筛选" value={ownerFilter} onChange={setOwnerFilter} options={users.map((user) => ({ value: String(user.id), label: user.name }))} placeholder="全部负责人" /></div></div><DataTable data={visibleItems} columns={[{ title: '项目', render: (_: any, r: Project) => <button className="primary-cell primary-cell-button" onClick={() => setSelected(r.id)}><strong>{r.name}</strong><span>{r.project_code || '未填写 OA / PI'}{r.end_date ? ` · 截止 ${r.end_date}` : ''}</span></button>, width: 250 }, { title: '状态', render: (_: any, r: Project) => <StatusTag value={statusLabel[r.status] || r.status} />, width: 100 }, { title: '负责人', render: (_: any, r: Project) => r.owner?.name || '未分配', width: 105 }, { title: '合作进度', render: (_: any, r: Project) => <div className="primary-cell"><strong>{r.campaign_count || 0} 个执行单</strong><span>{r.objective || '未填写项目目标'}</span></div>, width: 210 }, { title: '预算 / 实付', render: (_: any, r: Project) => <div className="primary-cell"><strong>{r.budget_amount == null ? '未设置预算' : `${r.budget_currency || 'CNY'} ${Number(r.budget_amount).toLocaleString()}`}</strong><span>实付 ¥{Number(r.actual_amount || 0).toLocaleString()}</span></div>, width: 150 }, ...(canEdit ? [{ title: '管理', render: (_: any, r: Project) => <button className="table-action" title="编辑项目信息" onClick={() => setEditing({ ...r, owner_id: r.owner_id || r.owner?.id })}><Pencil size={16} />编辑</button>, width: 80 }] : [])]} />{editing && <Dialog title={editing.id ? '编辑项目信息' : '新建推广项目'} onClose={() => setEditing(null)} onOk={() => void save()} footerStart={canManage && editing.id ? <div className="row-actions"><button className="table-action" onClick={() => void archiveProject()}><Archive size={15} />归档</button><Popover trigger={<Button icon={<MoreHorizontal size={16} />}>更多</Button>} align="start"><div className="record-action-menu"><button className="record-action-menu-danger" onClick={() => void deleteProject()}>永久删除<span>同时删除项目内执行数据</span></button></div></Popover></div> : undefined}><ProjectForm value={editing} users={users} setValue={setEditing} /></Dialog>}</section>;
}

function ProjectForm({ value, users, setValue }: { value: Partial<Project>; users: User[]; setValue: (value: Partial<Project>) => void }) { const set = (key: keyof Project, raw: any) => setValue({ ...value, [key]: raw }); return <div className="form-grid"><label>项目名称<Input value={value.name || ''} onChange={(e) => set('name', e.target.value)} /></label><label>项目编号 / OA PI<Input value={value.project_code || ''} onChange={(e) => set('project_code', e.target.value)} /></label><label>负责人<SelectField value={value.owner_id} onChange={(ownerId) => set('owner_id', ownerId ? Number(ownerId) : undefined)} options={users.map((user) => ({ key: String(user.id), label: user.name }))} placeholder="未分配" /></label><label>项目状态<SelectField value={value.status || 'Active'} onChange={(status) => set('status', status)} options={[{ key: 'Active', label: 'Active（进行中）' }, { key: 'Completed', label: 'Completed（已完成）' }, { key: 'Paused', label: 'Paused（已暂停）' }]} /></label><label>开始日期<Input type="date" value={value.start_date || ''} onChange={(e) => set('start_date', e.target.value || null)} /></label><label>结束日期<Input type="date" value={value.end_date || ''} onChange={(e) => set('end_date', e.target.value || null)} /></label><label>预算金额<Input type="number" value={value.budget_amount ?? ''} onChange={(e) => set('budget_amount', e.target.value ? Number(e.target.value) : null)} /></label><label>币种<Input value={value.budget_currency || 'CNY'} onChange={(e) => set('budget_currency', e.target.value)} /></label><label className="wide project-tag-field">内容识别 Tag<Input value={value.collaboration_tag || '#MAXSUN'} onChange={(e) => set('collaboration_tag', e.target.value)} onBlur={(e) => set('collaboration_tag', e.target.value.trim().startsWith('#') ? e.target.value.trim() : `#${e.target.value.trim()}`)} /><span className="field-hint">YouTube 视频标题或 Description 包含这个完整 Tag 即可；修改后下一轮扫描立即使用。</span></label><label className="wide">项目目标<textarea value={value.objective || ''} onChange={(e) => set('objective', e.target.value)} /></label><label className="wide">项目备注<textarea value={value.notes || ''} onChange={(e) => set('notes', e.target.value)} /></label></div>; }

function ProjectDetail({ id, onBack, canEdit, canManage }: { id: number; onBack: () => void; canEdit: boolean; canManage: boolean }) {
  const [data, setData] = useState<any>(null); const [loading, setLoading] = useState(true); const [loadError, setLoadError] = useState(''); const [kind, setKind] = useState<'shipment' | 'cost' | 'content' | 'activity' | null>(null); const [editing, setEditing] = useState<Partial<Project> | null>(null); const [editingCollaboration, setEditingCollaboration] = useState<Collaboration | null>(null); const [users, setUsers] = useState<User[]>([]);
  const load = async () => { setLoading(true); setLoadError(''); try { setData(await api<any>(`/api/projects/${id}`)); } catch (error) { setData(null); setLoadError(String(error)); } finally { setLoading(false); } };
  useEffect(() => { void load(); api<{ items: User[] }>('/api/users').then((x) => setUsers(x.items)).catch(() => {}); }, [id]);
  if (loading) return <section><PageHeader title="加载项目" action={<Button onClick={onBack}>返回项目</Button>} /><div className="loading-state">正在读取项目详情...</div></section>;
  if (loadError) return <section><PageHeader title="项目详情" action={<Button onClick={onBack}>返回项目</Button>} /><div className="error-state"><strong>读取项目详情失败</strong><span>请刷新重试；若问题持续出现，请保留当前项目名称和报错信息。</span><div><Button onClick={() => void load()}>重新加载</Button><Button onClick={onBack}>返回项目列表</Button></div></div></section>;
  if (!data) return <section><PageHeader title="项目详情" action={<Button onClick={onBack}>返回项目</Button>} /><Empty /></section>;
  const project: Project = data.project; const collaborations: Collaboration[] = data.campaigns || []; const summary = data.summary || {};
  const saveProject = async () => { if (!editing?.name?.trim()) return Notification.error({ message: '请填写项目名称' }); try { await api(`/api/projects/${id}`, { method: 'PUT', body: JSON.stringify({ ...editing, name: editing.name.trim() }) }); setEditing(null); await load(); Notification.success({ message: '项目信息已更新' }); } catch (error) { Notification.error({ message: '保存失败', description: String(error) }); } };
  const archiveProject = async () => { if (!await confirmAction(`确定归档项目“${project.name}”吗？\n\n归档后项目及其执行单会从日常列表、工作台和 KPI 中隐藏，可在“历史归档”恢复。`)) return; try { await api(`/api/projects/${id}/archive`, { method: 'POST' }); Notification.success({ message: '项目已归档' }); onBack(); } catch (error) { Notification.error({ message: '归档失败', description: String(error) }); } };
  const deleteProject = async () => { const rows = collaborations; const shipments = rows.reduce((sum, row) => sum + (row.shipments?.length || 0), 0); const costs = rows.reduce((sum, row) => sum + (row.cost_items?.length || 0), 0); const content = rows.reduce((sum, row) => sum + (row.deliverables?.length || 0), 0); const activities = rows.reduce((sum, row) => sum + (row.activities?.length || 0), 0); if (!await confirmAction(`永久删除项目“${project.name}”？\n\n将删除 ${rows.length} 条执行单、${shipments} 条寄样、${costs} 条费用、${content} 条内容和 ${activities} 条动态。媒体、联系人和产品不会删除。此操作不可撤销。`)) return; try { await api(`/api/projects/${id}`, { method: 'DELETE' }); Notification.success({ message: '项目已永久删除' }); onBack(); } catch (error) { Notification.error({ message: '删除失败', description: String(error) }); } };
  return <section><PageHeader title={project.name} action={<div className="page-actions">{canEdit && <Button icon={<Pencil size={16} />} onClick={() => setEditing({ ...project, owner_id: project.owner_id || project.owner?.id })}>编辑项目信息</Button>}<a className="export-link" href={`/api/projects/${id}/report.xlsx`}><Download size={16} />导出复盘</a><Button onClick={onBack}>返回项目</Button></div>} /><div className="project-hero"><div><span>项目编号 {project.project_code || '未填写'} · 负责人 {project.owner?.name || '未分配'}</span><h2>{project.objective || '尚未填写项目目标'}</h2></div><div className="project-totals"><span>预算 ¥{Number(project.budget_amount || 0).toLocaleString()}</span><strong>实付 ¥{Number(data.actual_amount || 0).toLocaleString()}</strong><span>差额 ¥{Number((project.budget_amount || 0) - (data.actual_amount || 0)).toLocaleString()}</span></div></div><section className="result-summary"><div><span>合作对象</span><strong>{summary.collaboration_count || 0}</strong></div><div><span>已发布 / 完成率</span><strong>{summary.published_count || 0} · {summary.completion_rate || 0}%</strong></div><div><span>3 日播放</span><strong>{Number(summary.three_day_views || 0).toLocaleString()}</strong><small>{summary.three_day_content_count || 0} 条已完成采集</small></div><div><span>3 日互动</span><strong>{Number((summary.three_day_likes || 0) + (summary.three_day_comments || 0)).toLocaleString()}</strong></div><div><span>3 日 CPV</span><strong>{summary.three_day_cpv == null ? '等待采集' : `¥${Number(summary.three_day_cpv).toLocaleString()}`}</strong><small>实付 ÷ 三日播放</small></div></section><div className="detail-actions">{canEdit && <><Button icon={<Truck size={16} />} onClick={() => setKind('shipment')}>登记寄样</Button><Button icon={<Wallet size={16} />} onClick={() => setKind('cost')}>登记费用</Button><Button icon={<ClipboardList size={16} />} onClick={() => setKind('content')}>登记内容</Button><Button onClick={() => setKind('activity')}>记录动态</Button></>}</div><DataTable data={collaborations} columns={[{ title: '合作对象', render: (_: any, r: Collaboration) => r.media?.name || r.media_id, width: 180 }, { title: '下一步', dataIndex: 'next_action', width: 180 }, { title: '跟进日期', dataIndex: 'follow_up_date', width: 120 }, { title: '负责人', render: (_: any, r: Collaboration) => r.owner?.name || '-', width: 100 }, { title: '执行状态', render: (_: any, r: Collaboration) => <StatusTag value={r.execution_status} />, width: 140 }, { title: '内容 / 3 日播放', render: (_: any, r: Collaboration) => r.deliverables?.[0]?.url ? <div className="primary-cell"><a href={r.deliverables[0].url} target="_blank">查看产出</a><span>{performanceSample(r.deliverables[0], 'day_3')?.views == null ? monitoringLabel(r.deliverables[0].monitoring_status) : Number(performanceSample(r.deliverables[0], 'day_3').views).toLocaleString()}</span></div> : '未登记', width: 140 }, { title: '费用', render: (_: any, r: Collaboration) => `¥${(r.cost_items || []).reduce((sum: number, x: any) => sum + Number(x.actual_amount || 0), 0).toLocaleString()}`, width: 120 }, ...(canEdit ? [{ title: '管理', render: (_: any, r: Collaboration) => <button className="table-action" onClick={() => setEditingCollaboration(r)}><Pencil size={15} />编辑</button>, width: 100 }] : [])]} />{kind && <AddRecord projectId={id} kind={kind} campaigns={collaborations} onClose={() => setKind(null)} onSaved={() => { setKind(null); load(); }} />}{editing && <Dialog title="编辑项目信息" onClose={() => setEditing(null)} onOk={() => void saveProject()}><ProjectForm value={editing} users={users} setValue={setEditing} /></Dialog>}{editingCollaboration && <CollaborationEditor value={editingCollaboration} onClose={() => setEditingCollaboration(null)} onSaved={() => { setEditingCollaboration(null); load(); }} />}</section>;
}

function LegacyAddRecord({ projectId, kind, campaigns, onClose, onSaved }: { projectId: number; kind: 'shipment' | 'cost' | 'content' | 'activity'; campaigns: Collaboration[]; onClose: () => void; onSaved: () => void }) {
  const [campaignId, setCampaignId] = useState<number | null>(campaigns[0]?.id || null);
  const [media, setMedia] = useState<Media[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [addresses, setAddresses] = useState<ShippingAddress[]>([]);
  const [mediaId, setMediaId] = useState<number | null>(campaigns[0]?.media_id || null);
  const [shipmentSource, setShipmentSource] = useState<'project' | 'library'>('project');
  const [productId, setProductId] = useState<number | null>(null);
  const [form, setForm] = useState<any>({ status: '待发货', cost_type: '评测费用', payment_status: '未付款', deliverable_type: 'Other', activity_type: '备注' });
  const set = (key: string, value: any) => setForm((current: any) => ({ ...current, [key]: value }));

  useEffect(() => {
    if (kind !== 'shipment') return;
    api<{ items: Media[] }>('/api/media?page_size=500').then((result) => setMedia(result.items));
    api<{ items: any[] }>('/api/products?page_size=500').then((result) => setProducts(result.items));
  }, [kind]);
  useEffect(() => {
    if (kind !== 'shipment' || !mediaId) { setAddresses([]); return; }
    api<ShippingAddress[]>(`/api/media/${mediaId}/shipping-addresses`).then((rows) => {
      setAddresses(rows);
      const selected = rows.find((row) => row.is_default) || rows[0];
      setForm((current: any) => ({ ...current, shipping_address_id: selected?.id || null, recipient_address: selected ? formatAddress(selected) : '' }));
    });
  }, [kind, mediaId]);

  const selectCampaign = (id: number | null) => {
    setCampaignId(id);
    const campaign = campaigns.find((item) => item.id === id);
    if (campaign) { setMediaId(campaign.media_id); setShipmentSource('project'); } else setMediaId(null);
  };
  const chooseLibrary = () => {
    setShipmentSource('library'); setCampaignId(null); setMediaId(null);
    setForm((current: any) => ({ ...current, shipping_address_id: null, recipient_address: '' }));
  };
  const chooseAddress = (value: string) => {
    const selected = addresses.find((row) => row.id === Number(value));
    setForm((current: any) => ({ ...current, shipping_address_id: selected?.id || null, recipient_address: selected ? formatAddress(selected) : '' }));
  };
  const save = async () => {
    try {
      if (kind !== 'shipment' && !campaignId) return Notification.error({ message: '请选择合作对象' });
      const base = { ...form, campaign_id: campaignId };
      if (kind === 'shipment') {
        const product = products.find((item) => item.id === productId);
        if (!mediaId) return Notification.error({ message: shipmentSource === 'project' ? '请从本项目合作对象中选择执行单' : '请从 KOL 媒体库选择合作对象' });
        await api(`/api/projects/${projectId}/shipments`, { method: 'POST', body: JSON.stringify({ ...form, media_id: mediaId, campaign_id: shipmentSource === 'project' ? campaignId : null, items: product ? [{ product_id: product.id, product_name: product.model, quantity: 1 }] : form.product_name ? [{ product_name: form.product_name, quantity: 1 }] : [] }) });
      }
      if (kind === 'cost') await api('/api/cost-items', { method: 'POST', body: JSON.stringify({ ...base, actual_amount: form.actual_amount ? Number(form.actual_amount) : null, planned_amount: form.planned_amount ? Number(form.planned_amount) : null }) });
      if (kind === 'content') await api('/api/deliverables', { method: 'POST', body: JSON.stringify(base) });
      if (kind === 'activity') await api('/api/activities', { method: 'POST', body: JSON.stringify(base) });
      onSaved();
    } catch (error) { Notification.error({ message: '保存失败', description: String(error) }); }
  };

  const shipmentOptions: LookupOption[] = campaigns.map((item) => ({ id: item.id, label: `${item.media?.name || `执行单 ${item.id}`} · ${item.execution_status}${item.owner?.name ? ` · ${item.owner.name}` : ''}`, search: `${item.media?.name || ''} ${item.media?.country || ''} ${item.execution_status} ${item.owner?.name || ''}` }));
  return <Dialog title={{ shipment: '登记寄样', cost: '登记费用', content: '登记内容产出', activity: '记录动态' }[kind]} onClose={onClose} onOk={save}>
    <div className="form-grid">
      {kind !== 'shipment' && <label className="wide">合作对象<EntityLookup value={campaignId} onChange={setCampaignId} options={campaignLookupOptions(campaigns)} placeholder="输入 KOL、国家、项目或状态" /></label>}
      {kind === 'shipment' && <>
        <label className="wide">本项目合作对象<EntityLookup value={shipmentSource === 'project' ? campaignId : null} onChange={selectCampaign} options={shipmentOptions} placeholder={campaigns.length ? '输入 KOL、状态或负责人匹配执行单' : '本项目尚未创建合作执行单'} /></label>
        <div className="wide shipment-source-note"><span>{shipmentSource === 'project' && campaignId ? '寄样将精确关联到选中的合作执行单。' : '没有对应执行单时，可从媒体库新增合作对象。'}</span><button type="button" className="link-button" onClick={chooseLibrary}>从媒体 / KOL 库另选</button></div>
        {shipmentSource === 'library' && <label className="wide">从媒体 / KOL 库选择<EntityLookup value={mediaId} onChange={setMediaId} options={mediaLookupOptions(media)} placeholder="输入名称、国家、渠道或主页链接" /></label>}
        {mediaId && <>
          <label className="wide">收件地址<SelectField value={form.shipping_address_id || ''} onChange={chooseAddress} options={addresses.map((row) => ({ key: String(row.id), label: `${row.is_default ? '默认 · ' : ''}${row.recipient_name || '未填写收件人'} · ${row.address_text}` }))} placeholder={addresses.length ? '选择地址档案' : '该媒体尚未登记地址'} /></label>
          <label className="wide">本次寄样收件信息<textarea value={form.recipient_address || ''} onChange={(event) => set('recipient_address', event.target.value)} placeholder="选择地址后可继续修改，本次保存为快照" /></label>
        </>}
        <label>OA / PI<Input value={form.oa_pi_number || ''} onChange={(event) => set('oa_pi_number', event.target.value)} /></label>
        <label>物流单号<Input value={form.tracking_number || ''} onChange={(event) => set('tracking_number', event.target.value)} /></label>
        <label>承运商<Input value={form.carrier || ''} onChange={(event) => set('carrier', event.target.value)} /></label>
        <label>物流状态<SelectField value={form.status} onChange={(value) => set('status', value)} options={shipmentStatusOptions.map((value) => ({ key: value, label: value }))} /></label>
        <label className="wide">产品库<EntityLookup value={productId} onChange={setProductId} options={products.map((item) => ({ id: item.id, label: item.model, search: `${item.model} ${item.full_name || ''} ${item.aliases || ''} ${item.platform || ''}` }))} placeholder="输入完整型号、别名或芯片组" /></label>
        <label className="wide">或输入新产品名称<Input value={form.product_name || ''} onChange={(event) => set('product_name', event.target.value)} /></label>
      </>}
      {kind === 'cost' && <>
        <label>费用类型<SelectField value={form.cost_type} onChange={(value) => set('cost_type', value)} options={['产品费用', '物流/关税', '评测费用', '其他费用'].map((value) => ({ key: value, label: value }))} /></label>
        <label>付款状态<SelectField value={form.payment_status} onChange={(value) => set('payment_status', value)} options={['未付款', '部分付款', '已付款', '无需付款'].map((value) => ({ key: value, label: value }))} /></label>
        <label>预算金额<Input value={form.planned_amount || ''} onChange={(event) => set('planned_amount', event.target.value)} /></label>
        <label>实付金额<Input value={form.actual_amount || ''} onChange={(event) => set('actual_amount', event.target.value)} /></label>
      </>}
      {kind === 'content' && <>
        <label>内容类型<Input value={form.deliverable_type || 'Other'} onChange={(event) => set('deliverable_type', event.target.value)} /></label>
        <label>内容链接<Input value={form.url || ''} onChange={(event) => set('url', event.target.value)} /></label>
        <label>播放 / 阅读<Input value={form.views || ''} onChange={(event) => set('views', event.target.value ? Number(event.target.value) : null)} /></label>
      </>}
      {kind === 'activity' && <label className="wide">内容<textarea value={form.content || ''} onChange={(event) => set('content', event.target.value)} /></label>}
    </div>
  </Dialog>;
}

function AddRecord({ projectId, kind, campaigns, onClose, onSaved }: { projectId: number; kind: 'shipment' | 'cost' | 'content' | 'activity'; campaigns: Collaboration[]; onClose: () => void; onSaved: () => void }) {
  const [campaignId, setCampaignId] = useState<number | null>(campaigns[0]?.id || null);
  const [form, setForm] = useState<any>({ deliverable_type: 'Other', url: '', published_at: '', impressions: null, views: null, likes: null, comments: null });
  if (kind !== 'content') return <LegacyAddRecord projectId={projectId} kind={kind} campaigns={campaigns} onClose={onClose} onSaved={onSaved} />;
  const set = (key: string, value: any) => setForm({ ...form, [key]: value });
  const save = async () => { if (!campaignId) return Notification.error({ message: '请选择合作对象' }); try { await api('/api/deliverables', { method: 'POST', body: JSON.stringify({ ...form, campaign_id: campaignId }) }); onSaved(); } catch (error) { Notification.error({ message: '保存失败', description: String(error) }); } };
  return <Dialog title="登记内容产出" onClose={onClose} onOk={() => void save()}><div className="form-grid"><label className="wide">合作对象<EntityLookup value={campaignId} onChange={setCampaignId} options={campaignLookupOptions(campaigns)} placeholder="输入 KOL、国家、项目或状态" /></label><label>内容类型<Input value={form.deliverable_type} onChange={(e) => set('deliverable_type', e.target.value)} /></label><label>发布时间<Input type="date" value={form.published_at} onChange={(e) => set('published_at', e.target.value || null)} /></label><label className="wide">内容链接<Input value={form.url} onChange={(e) => set('url', e.target.value)} /></label><label>曝光量<Input value={form.impressions || ''} onChange={(e) => set('impressions', e.target.value ? Number(e.target.value) : null)} /></label><label>播放 / 阅读<Input value={form.views || ''} onChange={(e) => set('views', e.target.value ? Number(e.target.value) : null)} /></label><label>点赞<Input value={form.likes || ''} onChange={(e) => set('likes', e.target.value ? Number(e.target.value) : null)} /></label><label>评论<Input value={form.comments || ''} onChange={(e) => set('comments', e.target.value ? Number(e.target.value) : null)} /></label></div></Dialog>;
}

export function CollaborationEditor({ value, onClose, onSaved, canManage = false }: { value: Collaboration; onClose: () => void; onSaved: () => void; canManage?: boolean }) {
  const [form, setForm] = useState<any>({ ...value, project_id: value.project_id, media_id: value.media_id, owner_id: value.owner_id, expected_publish_date: value.expected_publish_date || '', follow_up_date: value.follow_up_date || '', follow_up_priority: value.follow_up_priority || '普通', next_action: value.next_action || nextActionByStatus[value.execution_status] || '', notes: value.notes || '', collaboration_type: value.collaboration_type || '' });
  const [detail, setDetail] = useState<any>(value); const [activity, setActivity] = useState('');
  const [activeTab, setActiveTab] = useState<'overview' | 'shipment' | 'content' | 'cost' | 'activity'>('overview');
  const [recordKind, setRecordKind] = useState<'shipment' | 'cost' | 'content' | null>(null);
  const [advancing, setAdvancing] = useState<Collaboration | null>(null); const [statusAction, setStatusAction] = useState<{ action: 'cancel' | 'rollback'; reason: string } | null>(null);
  const [moreActionsOpen, setMoreActionsOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]); const [media, setMedia] = useState<Media[]>([]); const [users, setUsers] = useState<User[]>([]);
  const loadDetail = () => api<any>(`/api/collaborations/${value.id}`).then((result) => { setDetail(result); const shipment = result.shipments?.[0]; setForm((current: any) => ({ ...current, oa_pi_number: shipment?.oa_pi_number || '', tracking_number: shipment?.tracking_number || '' })); });
  useEffect(() => { void loadDetail(); api<{ items: Project[] }>('/api/projects?page_size=300').then((x) => setProjects(x.items)); api<{ items: Media[] }>('/api/media?page_size=500').then((x) => setMedia(x.items)); api<{ items: User[] }>('/api/users').then((x) => setUsers(x.items)).catch(() => {}); }, []);
  const save = async () => { if (!form.media_id) return Notification.error({ message: '请选择合作对象' }); try { const saved = await api<any>(`/api/collaborations/${value.id}`, { method: 'PATCH', body: JSON.stringify({ project_id: form.project_id || null, media_id: form.media_id, owner_id: form.owner_id || null, collaboration_type: form.collaboration_type || null, expected_publish_date: form.expected_publish_date || null, next_action: form.next_action || null, follow_up_date: form.follow_up_date || null, follow_up_priority: form.follow_up_priority || '普通', follow_up_done: Boolean(form.follow_up_done), oa_pi_number: form.oa_pi_number || null, tracking_number: form.tracking_number || null, notes: form.notes || null }) }); if (saved.workflow_warnings?.length) Notification.warning({ message: '已保存，跟进安排仍待完善', description: saved.workflow_warnings.join('；') }); else Notification.success({ message: '执行单与寄样信息已更新' }); onSaved(); } catch (error) { Notification.error({ message: '保存失败', description: String(error) }); } };
  const applyStatusResult = (result: Collaboration) => { setDetail(result); setForm((current: any) => ({ ...current, execution_status: result.execution_status, next_action: result.next_action || '', follow_up_done: result.follow_up_done })); };
  const runStatusAction = async () => { if (!statusAction?.reason.trim()) return Notification.error({ message: '请填写操作原因' }); try { const result = await api<Collaboration>(`/api/collaborations/${value.id}/status-action`, { method: 'POST', body: JSON.stringify(statusAction) }); setStatusAction(null); applyStatusResult(result); Notification.success({ message: statusAction.action === 'cancel' ? '合作已取消并留痕' : '已回退一个阶段' }); } catch (error) { Notification.error({ message: '状态操作失败', description: String(error) }); } };
  const runSimpleStatusAction = async (action: 'pause' | 'resume') => { try { const result = await api<Collaboration>(`/api/collaborations/${value.id}/status-action`, { method: 'POST', body: JSON.stringify({ action }) }); applyStatusResult(result); Notification.success({ message: action === 'pause' ? '合作已暂停' : `已恢复到“${result.execution_status}”` }); } catch (error) { Notification.error({ message: '状态操作失败', description: String(error) }); } };
  const quickAdvance = () => void advanceWithGuard({ ...detail, ...form, id: value.id }, applyStatusResult, setAdvancing);
  const addActivity = async () => { if (!activity.trim()) return; try { await api('/api/activities', { method: 'POST', body: JSON.stringify({ campaign_id: value.id, activity_type: '跟进记录', content: activity.trim() }) }); setActivity(''); await loadDetail(); Notification.success({ message: '跟进记录已添加' }); } catch (error) { Notification.error({ message: '记录失败', description: String(error) }); } };
  const archive = async () => { if (!await confirmAction(`确定归档合作执行单“${value.media?.name || value.id}”吗？\n\n归档后将从日常列表和工作台隐藏，可在“历史归档”恢复。`)) return; try { await api(`/api/campaigns/${value.id}/archive`, { method: 'POST' }); Notification.success({ message: '执行单已归档' }); onSaved(); } catch (error) { Notification.error({ message: '归档失败', description: String(error) }); } };
  const remove = async () => { try { const detail = await api<any>(`/api/collaborations/${value.id}`); if (!await confirmAction(`永久删除合作执行单“${value.media?.name || value.id}”？\n\n将删除 ${detail.shipments?.length || 0} 条寄样、${detail.cost_items?.length || 0} 条费用、${detail.deliverables?.length || 0} 条内容和 ${detail.activities?.length || 0} 条动态。媒体、联系人和产品不会删除。此操作不可撤销。`)) return; await api(`/api/campaigns/${value.id}`, { method: 'DELETE' }); Notification.success({ message: '执行单已永久删除' }); onSaved(); } catch (error) { Notification.error({ message: '删除失败', description: String(error) }); } };
  const currentIndex = workflowStatuses.indexOf(form.execution_status);
  const formHealth = workflowHealthOf(form);
  const shipments = detail.shipments || [];
  const deliverables = detail.deliverables || [];
  const costs = detail.cost_items || [];
  const activities = detail.activities || [];
  const plannedTotal = costs.reduce((sum: number, item: any) => sum + Number(item.planned_amount || 0), 0);
  const actualTotal = costs.reduce((sum: number, item: any) => sum + Number(item.actual_amount || 0), 0);
  const projectId = Number(form.project_id || value.project_id || 0);
  const tabs = [
    { key: 'overview', label: '概览', icon: <ClipboardList size={15} /> },
    { key: 'shipment', label: '寄样物流', count: shipments.length, icon: <Truck size={15} /> },
    { key: 'content', label: '内容产出', count: deliverables.length, icon: <CheckCircle2 size={15} /> },
    { key: 'cost', label: '费用结算', count: costs.length, icon: <Wallet size={15} /> },
    { key: 'activity', label: '合作动态', count: activities.length, icon: <RefreshCw size={15} /> },
  ] as const;
  const sectionHeading = (title: string, hint: string, action?: React.ReactNode) => <div className="collaboration-section-heading"><div><h3>{title}</h3><span>{hint}</span></div>{action}</div>;
  const emptyRecord = (title: string, hint: string) => <div className="detail-empty"><span>✦</span><strong>{title}</strong><p>{hint}</p></div>;

  return <>
    <Dialog contentClassName="collaboration-drawer" title={`合作执行 · ${value.media?.name || detail.media?.name || ''}`} onClose={onClose} onOk={() => void save()} footerStart={<div className="collaboration-actions">{detail.next_status && <Button type="primary" icon={<ArrowRight size={16} />} onClick={quickAdvance}>{advanceActionLabel[detail.next_status] || `推进到${detail.next_status}`}</Button>}{['已暂停', '已暂停/取消'].includes(form.execution_status) ? <Button onClick={() => void runSimpleStatusAction('resume')}>恢复合作</Button> : !['已结算', '已取消'].includes(form.execution_status) && <Button onClick={() => void runSimpleStatusAction('pause')}>暂停</Button>}{workflowStatuses.indexOf(form.execution_status) > 0 && <Button onClick={() => setStatusAction({ action: 'rollback', reason: '' })}>回退一步</Button>}{(!['已结算', '已取消'].includes(form.execution_status) || canManage) && <Popover open={moreActionsOpen} onOpenChange={setMoreActionsOpen} align="start" trigger={<Button>更多操作</Button>}><div className="record-action-menu">{!['已结算', '已取消'].includes(form.execution_status) && <button type="button" className="record-action-menu-warning" onClick={() => { setMoreActionsOpen(false); setStatusAction({ action: 'cancel', reason: '' }); }}>取消合作<span>停止跟进并保留历史</span></button>}{canManage && <><button type="button" onClick={() => { setMoreActionsOpen(false); void archive(); }}>归档执行单<span>移入历史归档，可恢复</span></button><button type="button" className="record-action-menu-danger" onClick={() => { setMoreActionsOpen(false); void remove(); }}>永久删除<span>删除寄样、费用和动态</span></button></>}</div></Popover>}</div>}>
      <div className="collaboration-detail">
        <div className="collaboration-detail-top">
          <div className="collaboration-context"><div><span>当前项目</span><strong>{projects.find((item) => item.id === Number(form.project_id))?.name || detail.project?.name || '未归属项目'}</strong></div><i /><div><span>负责人</span><strong>{users.find((item) => item.id === Number(form.owner_id))?.name || detail.owner?.name || '未分配'}</strong></div><i /><div><span>下一步</span><strong>{form.next_action || '待补充下一步行动'}</strong></div></div>
          <div className="workflow-rail">{workflowStatuses.map((status, index) => <div key={status} className={`${index < currentIndex ? 'done' : ''} ${status === form.execution_status ? 'active' : ''}`}><span>{index < currentIndex ? '✓' : index + 1}</span><strong>{status}</strong></div>)}</div>
        </div>
        <nav className="collaboration-tabs" aria-label="合作详情分区">{tabs.map((tab) => <button type="button" key={tab.key} className={activeTab === tab.key ? 'active' : ''} aria-current={activeTab === tab.key ? 'page' : undefined} onClick={() => setActiveTab(tab.key)}>{tab.icon}<span>{tab.label}</span>{'count' in tab && <em>{tab.count}</em>}</button>)}</nav>
        <div className="collaboration-tab-panel">
          {activeTab === 'overview' && <div className="collaboration-overview">
            {formHealth.warnings.length > 0 && <div className={`workflow-reminder workflow-reminder-${formHealth.code}`}><CheckCircle2 size={17} /><div><strong>{formHealth.label}</strong><span>{formHealth.warnings.join('；')}。本次仍可保存，不会阻塞紧急更新。</span></div></div>}
            <section className="detail-section">{sectionHeading('合作基础信息', '归属、负责人和当前执行安排')}<div className="form-grid execution-form"><label>推广项目<EntityLookup value={form.project_id} onChange={(nextProjectId) => setForm({ ...form, project_id: nextProjectId })} options={projectLookupOptions(projects)} placeholder="输入项目名称、OA/PI 或目标" /></label><label>合作对象<EntityLookup value={form.media_id} onChange={(mediaId) => setForm({ ...form, media_id: mediaId })} options={mediaLookupOptions(media)} placeholder="输入名称、国家、渠道或主页链接" /></label><label>负责人<SelectField value={form.owner_id} onChange={(ownerId) => setForm({ ...form, owner_id: ownerId ? Number(ownerId) : null })} options={users.map((user) => ({ key: String(user.id), label: user.name }))} placeholder="未分配" /></label><label>执行状态<div className="readonly-status"><StatusTag value={form.execution_status} /><small>本阶段 {detail.days_in_status ?? 0} 天 · 阶段变化自动留痕</small></div></label><label>推广形式<Input value={form.collaboration_type} onChange={(event) => setForm({ ...form, collaboration_type: event.target.value })} /></label><label>预计产出<Input type="date" value={form.expected_publish_date} onChange={(event) => setForm({ ...form, expected_publish_date: event.target.value })} /></label></div></section>
            <section className="detail-section detail-section-accent">{sectionHeading('下一步行动', '明确一个动作、一项日期和优先级')}<div className="form-grid followup-grid"><label className="wide next-action-field">行动内容<Input value={form.next_action} onChange={(event) => setForm({ ...form, next_action: event.target.value, follow_up_done: false })} /><button type="button" className="link-button" onClick={() => setForm({ ...form, next_action: nextActionByStatus[form.execution_status], follow_up_done: false })}>使用阶段建议</button></label><label>跟进日期<Input type="date" value={form.follow_up_date} onChange={(event) => setForm({ ...form, follow_up_date: event.target.value, follow_up_done: false })} /></label><label>优先级<SelectField value={form.follow_up_priority} onChange={(follow_up_priority) => setForm({ ...form, follow_up_priority })} options={['低', '普通', '高', '紧急'].map((x) => ({ key: x, label: x }))} /></label><div className="wide date-shortcuts" aria-label="跟进日期快捷选择"><span>快捷日期</span>{[[0, '今天'], [1, '明天'], [3, '3 天后'], [7, '7 天后']].map(([days, label]) => <button type="button" key={label} onClick={() => setForm({ ...form, follow_up_date: inputDateAfter(Number(days)), follow_up_done: false })}>{label}</button>)}</div></div></section>
            <section className="detail-section">{sectionHeading('合作备注', '补充约定、风险或仅供内部查看的信息')}<textarea className="detail-notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} placeholder="记录合作约定、特殊要求或风险…" /></section>
          </div>}

          {activeTab === 'shipment' && <div className="detail-record-page">
            {sectionHeading('寄样与物流', 'OA/PI、承运商、物流节点和寄送产品共用项目数据', projectId ? <Button icon={<Plus size={14} />} onClick={() => setRecordKind('shipment')}>新增寄样</Button> : undefined)}
            <section className="shipment-quick-edit"><div><strong>常用单据快捷更新</strong><span>保存后同步更新首条寄样记录</span></div><label>OA / PI<Input value={form.oa_pi_number || ''} onChange={(event) => setForm({ ...form, oa_pi_number: event.target.value })} placeholder="输入 OA / PI 编号" /></label><label>物流单号<Input value={form.tracking_number || ''} onChange={(event) => setForm({ ...form, tracking_number: event.target.value })} placeholder="输入快递或物流单号" /></label></section>
            {!projectId && <div className="inline-notice">当前合作尚未归属项目；保存项目归属后即可新增完整寄样记录。</div>}
            <div className="detail-record-list">{shipments.length ? shipments.map((item: any) => <article className="detail-record-card" key={item.id}><header><div><strong>{item.carrier || '寄样记录'}</strong><span>{item.created_at ? `登记于 ${formatDateTime(item.created_at)}` : '已登记'}</span></div><StatusTag value={item.status || '待发货'} /></header><div className="record-facts"><div><span>OA / PI</span><strong>{item.oa_pi_number || '—'}</strong></div><div><span>物流单号</span><strong>{item.tracking_number || '—'}</strong></div><div><span>发货 / 签收</span><strong>{[item.shipped_at, item.delivered_at].filter(Boolean).join(' → ') || '未登记日期'}</strong></div><div><span>寄送产品</span><strong>{item.items?.map((product: any) => `${product.product_name} × ${product.quantity || 1}`).join('、') || '未登记产品'}</strong></div></div>{item.recipient_address && <p className="record-note">收件信息 · {item.recipient_address}</p>}{item.notes && <p className="record-note">备注 · {item.notes}</p>}</article>) : emptyRecord('尚未登记寄样', '可先填写上方 OA/PI 或物流单号并保存，也可以新增完整寄样记录。')}</div>
          </div>}

          {activeTab === 'content' && <div className="detail-record-page">
            {sectionHeading('内容产出', '集中查看发布链接、发布日期和效果数据', <Button icon={<Plus size={14} />} onClick={() => setRecordKind('content')}>登记内容</Button>)}
            <div className="detail-record-list">{deliverables.length ? deliverables.map((item: any) => { const discovery = performanceSample(item, 'discovery'); const day1 = performanceSample(item, 'day_1'); const day3 = performanceSample(item, 'day_3'); const late = performanceSample(item, 'late_discovery'); return <article className="detail-record-card" key={item.id}><header><div><strong>{item.title || item.deliverable_type || '内容产出'}</strong><span>{item.published_at ? `发布于 ${item.published_at}` : '尚未登记发布时间'}{item.matched_tag ? ` · ${item.matched_tag} 自动关联` : ''}</span></div><div className="content-monitor-heading">{item.monitoring_status && <Tag color={item.monitoring_status === 'completed' ? 'app-teal' : undefined}>{monitoringLabel(item.monitoring_status)}</Tag>}{item.url && <a className="record-link" href={item.url} target="_blank" rel="noreferrer">查看内容</a>}</div></header>{item.platform_content_id ? <div className="record-facts record-facts-four"><div><span>发现时播放</span><strong>{Number((discovery || late)?.views || 0).toLocaleString()}</strong></div><div><span>首日播放</span><strong>{day1?.views == null ? '等待采集' : Number(day1.views).toLocaleString()}</strong></div><div><span>3 日播放</span><strong>{day3?.views == null ? item.monitoring_status === 'late_discovered' ? '发现较晚' : '等待采集' : Number(day3.views).toLocaleString()}</strong></div><div><span>3 日互动</span><strong>{day3 ? Number((day3.likes || 0) + (day3.comments || 0)).toLocaleString() : '—'}</strong></div></div> : <div className="record-facts record-facts-four"><div><span>曝光</span><strong>{Number(item.impressions || 0).toLocaleString()}</strong></div><div><span>播放 / 阅读</span><strong>{Number(item.views || 0).toLocaleString()}</strong></div><div><span>点赞</span><strong>{Number(item.likes || 0).toLocaleString()}</strong></div><div><span>评论</span><strong>{Number(item.comments || 0).toLocaleString()}</strong></div></div>}{item.data_updated_at && <p className="record-note">数据来源 · YouTube Data API v3 · 更新于 {formatDateTime(item.data_updated_at)}</p>}{item.performance_notes && <p className="record-note">效果备注 · {item.performance_notes}</p>}</article>; }) : emptyRecord('尚未登记内容产出', '发布后在这里登记链接和效果数据，项目复盘会引用同一份记录。')}</div>
          </div>}

          {activeTab === 'cost' && <div className="detail-record-page">
            {sectionHeading('费用与结算', '计划金额、实际支出和付款状态', <Button icon={<Plus size={14} />} onClick={() => setRecordKind('cost')}>登记费用</Button>)}
            <div className="cost-summary"><div><span>计划金额</span><strong>¥{plannedTotal.toLocaleString()}</strong></div><div><span>实际支出</span><strong>¥{actualTotal.toLocaleString()}</strong></div><div><span>预算差额</span><strong className={actualTotal > plannedTotal && plannedTotal > 0 ? 'over-budget' : ''}>¥{(plannedTotal - actualTotal).toLocaleString()}</strong></div></div>
            <div className="detail-record-list">{costs.length ? costs.map((item: any) => <article className="detail-record-card cost-record" key={item.id}><header><div><strong>{item.cost_type || '费用记录'}</strong><span>{item.reference_note || `登记于 ${formatDateTime(item.created_at)}`}</span></div><StatusTag value={item.payment_status || '未付款'} /></header><div className="record-facts"><div><span>计划金额</span><strong>{item.currency || 'CNY'} {Number(item.planned_amount || 0).toLocaleString()}</strong></div><div><span>实际支出</span><strong>{item.currency || 'CNY'} {Number(item.actual_amount || 0).toLocaleString()}</strong></div></div></article>) : emptyRecord('尚未登记费用', '登记评测费、产品费、物流关税等支出，便于项目统一核算。')}</div>
          </div>}

          {activeTab === 'activity' && <div className="detail-record-page activity-page">
            {sectionHeading('合作动态', '状态变化和人工跟进按时间统一留痕')}
            <div className="activity-composer activity-composer-wide"><textarea value={activity} onChange={(event) => setActivity(event.target.value)} placeholder="记录邮件回复、电话结论或风险…" /><Button type="primary" onClick={() => void addActivity()}>添加记录</Button></div>
            <div className="activity-timeline">{activities.length ? [...activities].sort((a: any, b: any) => String(b.created_at).localeCompare(String(a.created_at))).map((item: any) => <div key={item.id}><i /><article><strong>{item.activity_type}</strong><p>{item.content}</p><small>{item.user?.name || '系统'} · {formatDateTime(item.created_at)}</small></article></div>) : emptyRecord('还没有动态记录', '添加邮件回复、沟通结论或风险，后续状态变化也会自动留痕。')}</div>
          </div>}
        </div>
      </div>
    </Dialog>
    {recordKind && <AddRecord projectId={projectId} kind={recordKind} campaigns={[{ ...detail, ...form, id: value.id }]} onClose={() => setRecordKind(null)} onSaved={() => { setRecordKind(null); void loadDetail(); }} />}
    {advancing && <AdvanceCollaborationDialog item={advancing} onClose={() => setAdvancing(null)} onOpen={() => setAdvancing(null)} onAdvanced={(result) => { setAdvancing(null); applyStatusResult(result); }} />}
    {statusAction && <Dialog variant="modal" contentClassName={`status-action-dialog ${statusAction.action === 'cancel' ? 'status-action-dialog-danger' : ''}`} title={statusAction.action === 'cancel' ? '取消这次合作？' : '回退一个阶段'} onClose={() => setStatusAction(null)} onOk={() => void runStatusAction()} okLabel={statusAction.action === 'cancel' ? '确认取消' : '确认回退'} okType={statusAction.action === 'cancel' ? 'danger' : 'primary'}><div className="status-action-copy"><strong>{statusAction.action === 'cancel' ? '取消后将停止日常跟进，但历史记录仍会保留。' : `将从“${form.execution_status}”回到上一个阶段。`}</strong><span>{statusAction.action === 'cancel' ? '如果只是暂时搁置，建议关闭弹窗后选择“暂停”。' : '请用一句话说明回退依据，方便团队成员理解。'}</span></div><label className="action-reason">{statusAction.action === 'cancel' ? '取消原因' : '回退原因'}<textarea autoFocus value={statusAction.reason} onChange={(event) => setStatusAction({ ...statusAction, reason: event.target.value })} placeholder={statusAction.action === 'cancel' ? '例如：达人明确拒绝本次合作' : '例如：收件地址需要重新确认'} /></label></Dialog>}
  </>;
}

function LegacyExecution({ canEdit }: { canEdit: boolean }) {
  const [items, setItems] = useState<Collaboration[]>([]); const [form, setForm] = useState<Partial<Collaboration> | null>(null); const [projects, setProjects] = useState<Project[]>([]); const [media, setMedia] = useState<Media[]>([]); const [users, setUsers] = useState<User[]>([]);
  const load = () => api<{ items: Collaboration[] }>('/api/campaigns?page_size=200').then((x) => setItems(x.items)); useEffect(() => { load(); api<{ items: Project[] }>('/api/projects').then((x) => setProjects(x.items)); api<{ items: Media[] }>('/api/media?page_size=300').then((x) => setMedia(x.items)); api<{ items: User[] }>('/api/users').then((x) => setUsers(x.items)).catch(() => {}); }, []);
  const save = async () => { if (!form?.media_id) return Notification.error({ message: '请选择合作对象' }); try { await api(form.id ? `/api/campaigns/${form.id}` : '/api/campaigns', { method: form.id ? 'PUT' : 'POST', body: JSON.stringify({ ...form, media_id: Number(form.media_id), project_id: form.project_id ? Number(form.project_id) : null, owner_id: form.owner_id ? Number(form.owner_id) : null, stage: form.execution_status === '已发布' ? 'Published' : 'Not Started', sample_status: 'Not Needed', brief_sent: false }) }); setForm(null); load(); } catch (e) { Notification.error({ message: '保存失败', description: String(e) }); } };
  return <section><PageHeader title="合作执行单" action={canEdit && <Button type="primary" icon={<Plus size={16} />} onClick={() => setForm({ execution_status: '待确认', collaboration_type: '' })}>新建执行单</Button>} /><DataTable data={items} columns={[{ title: '项目', render: (_: any, r: Collaboration) => r.project?.name || '未归属', width: 180 }, { title: 'KOL / 媒体', render: (_: any, r: Collaboration) => r.media?.name || '-', width: 180 }, { title: '负责人', render: (_: any, r: Collaboration) => r.owner?.name || '-', width: 110 }, { title: '推广形式', dataIndex: 'collaboration_type', width: 150 }, { title: '状态', render: (_: any, r: Collaboration) => <StatusTag value={r.execution_status} />, width: 140 }, { title: '预计产出', dataIndex: 'expected_publish_date', width: 120 }]} />{form && <Dialog title={form.id ? '编辑执行单' : '新建合作执行单'} onClose={() => setForm(null)} onOk={save}><div className="form-grid"><label>推广项目<SelectField value={form.project_id} onChange={(x) => setForm({ ...form, project_id: x ? Number(x) : undefined })} options={projects.map((x) => ({ key: String(x.id), label: `${x.name}${x.project_code ? ` · ${x.project_code}` : ''}` }))} /></label><label>合作对象<SelectField value={form.media_id} onChange={(x) => setForm({ ...form, media_id: Number(x) })} options={media.map((x) => ({ key: String(x.id), label: `${x.name}${x.country ? ` · ${x.country}` : ''}` }))} /></label><label>负责人<SelectField value={form.owner_id} onChange={(x) => setForm({ ...form, owner_id: x ? Number(x) : undefined })} options={users.map((x) => ({ key: String(x.id), label: x.name }))} /></label><label>执行状态<div className="readonly-status"><StatusTag value="待确认" /><small>新合作统一从待确认开始</small></div></label><label>推广形式<Input value={form.collaboration_type || ''} onChange={(e) => setForm({ ...form, collaboration_type: e.target.value })} /></label><label>预计产出<Input type="date" value={form.expected_publish_date || ''} onChange={(e) => setForm({ ...form, expected_publish_date: e.target.value || undefined })} /></label><label className="wide">合作备注<textarea value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label></div></Dialog>}</section>;
}

function AdvanceCollaborationDialog({ item, onClose, onAdvanced, onOpen }: { item: Collaboration; onClose: () => void; onAdvanced: (result: Collaboration) => void; onOpen: (item: Collaboration) => void }) {
  const [detail, setDetail] = useState<Collaboration>(item);
  const [form, setForm] = useState<any>({ follow_up_date: item.next_status === '已结算' ? '' : inputDateAfter(3), no_payment_required: false });
  const [loading, setLoading] = useState(true);
  useEffect(() => { api<Collaboration>(`/api/collaborations/${item.id}`).then(setDetail).catch(() => Notification.error({ message: '读取推进条件失败' })).finally(() => setLoading(false)); }, [item.id]);
  const requirements = new Set(detail.advance_requirements || []);
  const needsManualSettlement = requirements.has('settle_costs');
  const set = (key: string, value: any) => setForm((current: any) => ({ ...current, [key]: value }));
  const advance = async () => {
    if (!detail.next_status) return;
    try {
      const result = await api<Collaboration>(`/api/collaborations/${item.id}/advance`, { method: 'POST', body: JSON.stringify({ target_status: detail.next_status, ...form, follow_up_date: form.follow_up_date || null }) });
      onAdvanced(result);
      Notification.success({ message: `已${advanceActionLabel[detail.next_status] || `推进到${detail.next_status}`}`, description: '补充资料和阶段变化已自动记录' });
    } catch (error) {
      Notification.error({ message: '暂时无法推进', description: String(error) });
    }
  };
  const openDetail = () => { onClose(); onOpen(detail); };
  return <Dialog variant="modal" contentClassName="advance-dialog" title={`补充资料 · ${detail.media?.name || item.media?.name || ''}`} onClose={onClose} onOk={!loading && detail.next_status && !needsManualSettlement ? () => void advance() : undefined} okLabel={advanceActionLabel[detail.next_status || ''] || `推进到${detail.next_status || ''}`} footerStart={<Button onClick={openDetail}>打开完整详情</Button>}>
    {loading ? <div className="advance-loading">正在检查最新资料…</div> : !detail.next_status ? <div className="advance-complete"><CheckCircle2 size={22} /><strong>当前合作已完成执行流程</strong></div> : <div className="advance-panel">
      <div className="advance-route"><span>{detail.execution_status}</span><ArrowRight size={18} /><strong>{detail.next_status}</strong></div>
      <p>补齐当前业务节点需要的资料后，即可继续推进；系统会自动记录本次变化。</p>
      {(detail.advance_blockers || []).length > 0 ? <div className="advance-check advance-check-blocked"><strong>还差这些资料</strong>{detail.advance_blockers!.map((blocker) => <span key={blocker}>· {blocker}</span>)}</div> : <div className="advance-check advance-check-ready"><CheckCircle2 size={17} /><div><strong>资料已完整</strong><span>可以继续到下一阶段</span></div></div>}
      <div className="form-grid advance-fields">
        {requirements.has('tracking_number') && <><label>物流单号<Input aria-label="物流单号" value={form.tracking_number || ''} onChange={(event) => set('tracking_number', event.target.value)} placeholder="必填" /></label><label>承运商（选填）<Input value={form.carrier || ''} onChange={(event) => set('carrier', event.target.value)} /></label></>}
        {requirements.has('delivered_at') && <label className="wide">签收日期<Input aria-label="签收日期" type="date" value={form.delivered_at || ''} onChange={(event) => set('delivered_at', event.target.value)} /></label>}
        {requirements.has('content_title') && <label className="wide">待审核内容<Input aria-label="待审核内容" value={form.content_title || ''} onChange={(event) => set('content_title', event.target.value)} placeholder="例如：首版视频 / 文案初稿" /></label>}
        {requirements.has('publication_url') && <label className="wide">发布链接<Input aria-label="发布链接" value={form.publication_url || ''} onChange={(event) => set('publication_url', event.target.value)} placeholder="https://" /></label>}
        {requirements.has('published_at') && <label>发布日期<Input aria-label="发布日期" type="date" value={form.published_at || ''} onChange={(event) => set('published_at', event.target.value)} /></label>}
        {requirements.has('no_payment_required') && <label className="wide advance-confirm"><input aria-label="确认本次合作无需付款" type="checkbox" checked={Boolean(form.no_payment_required)} onChange={(event) => set('no_payment_required', event.target.checked)} /><span><strong>确认本次合作无需付款</strong><small>系统会生成一条“无需付款”的零金额结算记录</small></span></label>}
        {detail.next_status !== '已结算' && <label className="wide">推进后的跟进日期（选填）<Input type="date" value={form.follow_up_date || ''} onChange={(event) => set('follow_up_date', event.target.value)} /></label>}
      </div>
      {needsManualSettlement && <div className="inline-notice">仍有未完成付款的费用记录。请打开完整详情处理付款状态后，再返回推进。</div>}
    </div>}
  </Dialog>;
}

export function ExecutionBoard({ items, onOpen, canEdit = false, onChanged = () => undefined }: { items: Collaboration[]; onOpen: (item: Collaboration) => void; canEdit?: boolean; onChanged?: () => void }) {
  const [advancing, setAdvancing] = useState<Collaboration | null>(null);
  const lanes = statusOptions;
  return <><div className="execution-board">{lanes.map((status) => {
    const laneItems = items.filter((item) => item.execution_status === status);
    return <section className="execution-lane" key={status}><header><span>{status}</span><strong>{laneItems.length}</strong></header><div>{laneItems.map((item) => {
      const shipment = item.shipments?.find((entry: any) => entry.tracking_number || entry.oa_pi_number);
      return <article className="execution-card" key={item.id}><button type="button" className="execution-card-main" onClick={() => onOpen(item)}><div className="execution-card-title"><strong>{item.media?.name || '未命名合作对象'}</strong><WorkflowHealthBadge item={item} /></div><span>{item.project?.name || '未归属项目'}</span><p>{item.next_action || '待补充下一步行动'}</p><footer><span>{item.owner?.name || '未分配'}</span><span>{item.follow_up_date || '未排期'}</span></footer>{shipment && <small>{shipment.oa_pi_number ? `OA/PI · ${shipment.oa_pi_number}` : `物流 · ${shipment.tracking_number}`}</small>}</button>{item.next_status && <div className={`execution-card-advance ${item.advance_ready ? 'ready' : 'blocked'}`}><span>{item.advance_ready ? `下一步 · ${advanceActionLabel[item.next_status] || item.next_status}` : item.advance_blockers?.[0] || '需补充资料'}</span>{canEdit && <button type="button" onClick={() => void advanceWithGuard(item, () => onChanged(), setAdvancing)}>{advanceActionLabel[item.next_status] || '推进'}<ArrowRight size={13} /></button>}</div>}</article>;
    })}{!laneItems.length && <div className="execution-lane-empty">暂无合作</div>}</div></section>;
  })}</div>{advancing && <AdvanceCollaborationDialog item={advancing} onClose={() => setAdvancing(null)} onOpen={onOpen} onAdvanced={() => { setAdvancing(null); onChanged(); }} />}</>;
}

function Execution({ canEdit, canManage }: { canEdit: boolean; canManage: boolean }) {
  const [mode, setMode] = useState<'tasks' | 'all' | 'board'>('tasks');
  const [items, setItems] = useState<Collaboration[]>([]);
  const [form, setForm] = useState<Partial<Collaboration> | null>(null);
  const [editing, setEditing] = useState<Collaboration | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [refreshToken, setRefreshToken] = useState(0);
  const [taskQueue, setTaskQueue] = useState('today');
  const [taskQueueResolved, setTaskQueueResolved] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [media, setMedia] = useState<Media[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const load = () => api<{ items: Collaboration[] }>('/api/campaigns?page_size=500').then((result) => setItems(result.items));
  useEffect(() => {
    void load();
    api<{ items: Project[] }>('/api/projects?page_size=300').then((result) => setProjects(result.items));
    api<{ items: Media[] }>('/api/media?page_size=500').then((result) => setMedia(result.items));
    api<{ items: User[] }>('/api/users').then((result) => setUsers(result.items)).catch(() => {});
  }, []);
  const refresh = () => { setRefreshToken((value) => value + 1); void load(); };
  const openEditing = async (id: number | Collaboration) => {
    try {
      setEditing(typeof id === 'number' ? await api<Collaboration>(`/api/collaborations/${id}`) : id);
    } catch {
      Notification.error({ message: '读取合作详情失败' });
    }
  };
  const save = async () => {
    if (!form?.media_id) return Notification.error({ message: '请从匹配结果中选择合作对象' });
    const health = workflowHealthOf(form);
    try {
      await api('/api/campaigns', { method: 'POST', body: JSON.stringify({ ...form, media_id: Number(form.media_id), project_id: form.project_id ? Number(form.project_id) : null, owner_id: form.owner_id ? Number(form.owner_id) : null, stage: form.execution_status === '已发布' ? 'Published' : 'Not Started', sample_status: 'Not Needed', brief_sent: false }) });
      setForm(null);
      refresh();
      if (health.warnings.length) Notification.warning({ message: '合作已创建，跟进安排仍待完善', description: health.warnings.join('；') }); else Notification.success({ message: '合作已创建' });
    } catch (error) {
      Notification.error({ message: '保存失败', description: String(error) });
    }
  };
  const beginCreate = () => setForm({ execution_status: '待确认', next_action: nextActionByStatus['待确认'], follow_up_priority: '普通', collaboration_type: '', project_id: undefined, media_id: undefined, owner_id: undefined });
  const normalizedSearch = search.trim().toLowerCase();
  const matchesSearch = (item: Collaboration) => !normalizedSearch || [item.media?.name, item.media?.country, item.media?.platform_type, item.project?.name, item.next_action, item.owner?.name, item.collaboration_type, item.shipments?.map((entry: any) => `${entry.oa_pi_number || ''} ${entry.tracking_number || ''}`).join(' ')].some((value) => String(value || '').toLowerCase().includes(normalizedSearch));
  const searchedItems = items.filter(matchesSearch);
  const visibleItems = searchedItems.filter((item) => !statusFilter || item.execution_status === statusFilter);
  const newFormHealth = form ? workflowHealthOf(form) : null;
  const viewSwitch = <div className="execution-view-switch" role="tablist" aria-label="合作执行视图">{([['tasks', '今日待办'], ['all', '全部合作'], ['board', '阶段看板']] as const).map(([key, label]) => <button key={key} role="tab" aria-selected={mode === key} className={mode === key ? 'active' : ''} onClick={() => setMode(key)}>{label}</button>)}</div>;
  const dialogs = <>
    {form && <Dialog title="新建合作" onClose={() => setForm(null)} onOk={() => void save()}><div className="form-grid">
      {newFormHealth?.warnings.length ? <div className={`wide workflow-reminder workflow-reminder-${newFormHealth.code}`}><CheckCircle2 size={17} /><div><strong>{newFormHealth.label}</strong><span>{newFormHealth.warnings.join('；')}。仍可先保存并稍后补充。</span></div></div> : null}
      <label>推广项目<EntityLookup value={form.project_id} onChange={(projectId) => setForm({ ...form, project_id: projectId || undefined })} options={projectLookupOptions(projects)} placeholder="输入项目名称、OA/PI 或目标" /></label>
      <label>合作对象<EntityLookup value={form.media_id} onChange={(mediaId) => setForm({ ...form, media_id: mediaId || undefined })} options={mediaLookupOptions(media)} placeholder="输入名称、国家、渠道或主页链接" /></label>
      <label>负责人<SelectField value={form.owner_id} onChange={(value) => setForm({ ...form, owner_id: value ? Number(value) : undefined })} options={users.map((item) => ({ key: String(item.id), label: item.name }))} placeholder="未分配" /></label>
      <label>执行状态<div className="readonly-status"><StatusTag value="待确认" /><small>新合作统一从待确认开始</small></div></label>
      <label>推广形式<Input value={form.collaboration_type || ''} onChange={(event) => setForm({ ...form, collaboration_type: event.target.value })} /></label>
      <label>预计产出<Input type="date" value={form.expected_publish_date || ''} onChange={(event) => setForm({ ...form, expected_publish_date: event.target.value || undefined })} /></label>
      <label className="wide">下一步行动<Input value={form.next_action || ''} onChange={(event) => setForm({ ...form, next_action: event.target.value })} /></label>
      <label>跟进日期<Input type="date" value={form.follow_up_date || ''} onChange={(event) => setForm({ ...form, follow_up_date: event.target.value || undefined })} /><span className="date-shortcuts">{[[0, '今天'], [1, '明天'], [3, '3 天后'], [7, '7 天后']].map(([days, label]) => <button type="button" key={label} onClick={() => setForm({ ...form, follow_up_date: inputDateAfter(Number(days)) })}>{label}</button>)}</span></label>
      <label>优先级<SelectField value={form.follow_up_priority} onChange={(follow_up_priority) => setForm({ ...form, follow_up_priority })} options={['低', '普通', '高', '紧急'].map((value) => ({ key: value, label: value }))} /></label>
      <label className="wide">合作备注<textarea value={form.notes || ''} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
    </div></Dialog>}
    {editing && <CollaborationEditor value={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); refresh(); }} canManage={canManage} />}
  </>;
  return <section className="execution-page"><PageHeader title="合作执行" subtitle="聚焦今日待办，也能随时查看完整合作与阶段进度 ✦" /><div className="workbench-toolbar execution-fixed-toolbar">{canEdit && <Button type="primary" icon={<Plus size={15} />} onClick={beginCreate}>新建</Button>}{viewSwitch}<label className="inline-filter"><Filter size={14} /><Select compact ariaLabel="筛选执行状态" value={statusFilter} onChange={setStatusFilter} options={statusOptions.map((option) => ({ value: option, label: option }))} placeholder="全部状态" /></label><label className="workbench-search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索创作者、项目、OA/PI 或物流单号" /></label><Button className="refresh-button" icon={<RefreshCw size={14} />} onClick={refresh} aria-label="刷新" /></div><ExecutionStatusBar items={items} value={statusFilter} onChange={setStatusFilter} /><div className="execution-view-content">{mode === 'tasks' ? <Workbench canEdit={canEdit} status={statusFilter} search={search} refreshToken={refreshToken} queue={taskQueue} autoResolveQueue={!taskQueueResolved} onQueueResolved={() => setTaskQueueResolved(true)} onQueueChange={setTaskQueue} onOpen={(id) => void openEditing(id)} /> : mode === 'all' ? <><div className="execution-content-heading"><div><strong>全部合作 · {visibleItems.length}</strong><span>集中查看完整档案、下一步行动与物流信息</span></div></div><DataTable data={visibleItems} columns={[{ title: '项目 / 合作对象', render: (_: any, row: Collaboration) => <button type="button" className="primary-cell primary-cell-button" onClick={() => void openEditing(row)}><strong>{row.media?.name || '-'}</strong><span>{row.project?.name || '未归属项目'}</span></button>, width: 220 }, { title: '当前阶段', render: (_: any, row: Collaboration) => <StatusTag value={row.execution_status} />, width: 130 }, { title: '下一步行动', render: (_: any, row: Collaboration) => <div className="primary-cell next-action-summary"><strong>{row.next_action || '待补充下一步行动'}</strong><span className={workflowHealthOf(row).code === 'overdue' ? 'overdue-text' : ''}>{row.follow_up_date || '未设置跟进日期'}</span><WorkflowHealthBadge item={row} /></div>, width: 270 }, { title: 'OA / PI · 物流', render: (_: any, row: Collaboration) => <ShipmentQuickInfo row={row} />, width: 230 }, { title: '负责人', render: (_: any, row: Collaboration) => row.owner?.name || '未分配', width: 95 }, { title: '预计产出', dataIndex: 'expected_publish_date', width: 105 }, ...(canEdit ? [{ title: '管理', render: (_: any, row: Collaboration) => <button className="table-action" onClick={() => void openEditing(row)}><Pencil size={15} />推进</button>, width: 82 }] : [])]} /></> : <ExecutionBoard items={visibleItems} canEdit={canEdit} onChanged={refresh} onOpen={(item) => void openEditing(item)} />}</div>{dialogs}</section>;
}
function ArchiveManager({ canManage }: { canManage: boolean }) {
  const [projects, setProjects] = useState<any[]>([]); const [campaigns, setCampaigns] = useState<any[]>([]); const [detail, setDetail] = useState<any>(null); const [tab, setTab] = useState<'projects' | 'campaigns'>('projects'); const [query, setQuery] = useState(''); const [source, setSource] = useState('');
  const load = () => { api<{ items: any[] }>('/api/projects?history_only=true&page_size=300').then((x) => setProjects(x.items)); api<{ items: any[] }>('/api/campaigns?history_only=true&page_size=500').then((x) => setCampaigns(x.items)); };
  useEffect(() => { void load(); }, []);
  const run = async (url: string, success: string) => { try { await api(url, { method: 'POST' }); await load(); Notification.success({ message: success }); } catch (error) { Notification.error({ message: '操作失败', description: String(error) }); } };
  const remove = async (url: string, message: string) => { if (!await confirmAction(message)) return; try { await api(url, { method: 'DELETE' }); setDetail(null); await load(); Notification.success({ message: '已永久删除' }); } catch (error) { Notification.error({ message: '删除失败', description: String(error) }); } };
  const projectRows = projects.filter((row) => (!source || (source === 'manual' ? row.is_archived : !row.is_archived)) && (!query || `${row.name} ${row.project_code || ''}`.toLowerCase().includes(query.toLowerCase()))); const campaignRows = campaigns.filter((row) => (!source || (source === 'manual' ? row.archived_at : !row.archived_at)) && (!query || `${row.project?.name || ''} ${row.media?.name || ''}`.toLowerCase().includes(query.toLowerCase())));
  const projectColumns = [{ title: '项目', render: (_: any, row: any) => <div className="primary-cell"><strong>{row.name}</strong><span>{row.project_code || '未填写 OA / PI'}</span></div>, width: 300 }, { title: '归档来源', render: (_: any, row: any) => row.is_archived ? '手动归档' : '历史导入', width: 130 }, { title: '执行单', render: (_: any, row: any) => `${row.campaign_count || 0} 条`, width: 110 }, { title: '管理', render: (_: any, row: any) => canManage ? <div className="row-actions">{row.is_archived && <button className="table-action" onClick={() => void run(`/api/projects/${row.id}/restore`, '项目已恢复')}>恢复</button>}<Popover align="end" trigger={<button className="icon-action" aria-label={`管理 ${row.name}`}><MoreHorizontal size={18} /></button>}><div className="record-action-menu"><button className="record-action-menu-danger" onClick={() => void remove(`/api/projects/${row.id}`, `永久删除项目“${row.name}”及其 ${row.campaign_count || 0} 条执行单？此操作不可撤销。`)}>永久删除<span>同时清除项目内全部执行数据</span></button></div></Popover></div> : '仅管理员可管理', width: 130 }];
  const campaignColumns = [{ title: '合作执行', render: (_: any, row: any) => <div className="primary-cell"><strong>{row.media?.name || '-'}</strong><span>{row.project?.name || '历史导入'}</span></div>, width: 300 }, { title: '归档来源', render: (_: any, row: any) => row.archived_at ? '手动归档' : '历史导入', width: 130 }, { title: '状态', render: (_: any, row: any) => <StatusTag value={row.execution_status} />, width: 140 }, { title: '管理', render: (_: any, row: any) => <div className="row-actions"><button className="table-action" onClick={async () => { try { setDetail(await api<any>(`/api/collaborations/${row.id}`)); } catch { Notification.error({ message: '读取执行单详情失败' }); } }}>查看</button>{canManage && <>{row.archived_at && <button className="table-action" onClick={() => void run(`/api/campaigns/${row.id}/restore`, '执行单已恢复')}>恢复</button>}<Popover align="end" trigger={<button className="icon-action" aria-label={`管理 ${row.media?.name || row.id}`}><MoreHorizontal size={18} /></button>}><div className="record-action-menu"><button className="record-action-menu-danger" onClick={() => void remove(`/api/campaigns/${row.id}`, `永久删除合作执行单“${row.media?.name || row.id}”？此操作不可撤销。`)}>永久删除<span>清除寄样、费用、内容和动态</span></button></div></Popover></>}</div>, width: 210 }];
  return <section className="resource-page"><PageHeader title="历史归档" subtitle="集中查看退出日常工作区的数据，需要时恢复，永久删除则收进更多操作" action={<Button className="refresh-button" icon={<RefreshCw size={16} />} onClick={() => void load()} aria-label="刷新归档" />} /><div className="resource-summary-grid"><div><span>归档项目</span><strong>{projects.length}</strong></div><div><span>归档执行单</span><strong>{campaigns.length}</strong></div><div><span>可恢复记录</span><strong>{projects.filter((row) => row.is_archived).length + campaigns.filter((row) => row.archived_at).length}</strong><small>手动归档记录</small></div></div><div className="resource-toolbar"><div className="resource-tabs" role="tablist"><button type="button" className={tab === 'projects' ? 'active' : ''} onClick={() => setTab('projects')}>项目<span>{projects.length}</span></button><button type="button" className={tab === 'campaigns' ? 'active' : ''} onClick={() => setTab('campaigns')}>合作执行单<span>{campaigns.length}</span></button></div><div className="resource-filters"><label className="resource-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目或合作对象" /></label><Select compact ariaLabel="按归档来源筛选" value={source} onChange={setSource} options={[{ value: 'manual', label: '手动归档' }, { value: 'import', label: '历史导入' }]} placeholder="全部来源" /></div></div>{tab === 'projects' ? <DataTable data={projectRows} columns={projectColumns} /> : <DataTable data={campaignRows} columns={campaignColumns} />}{detail && <Dialog variant="modal" title={`执行单详情 · ${detail.media?.name || ''}`} onClose={() => setDetail(null)}><div className="history-detail"><div><span>项目</span><strong>{detail.project?.name || '-'}</strong></div><div><span>状态</span><strong>{detail.execution_status}</strong></div><div><span>寄样</span><strong>{detail.shipments?.map((item: any) => item.tracking_number || item.oa_pi_number || item.status).join('；') || '未登记'}</strong></div><div><span>费用</span><strong>{detail.cost_items?.map((item: any) => `${item.cost_type} ¥${item.actual_amount || 0}`).join('；') || '未登记'}</strong></div></div></Dialog>}</section>;
}

function Library({ type, canEdit, canManage }: { type: 'media' | 'products' | 'contacts'; canEdit: boolean; canManage: boolean }) { if (type === 'media') return <MediaManagerV2 canEdit={canEdit} canManage={canManage} />; if (type === 'contacts') return <ContactManager canEdit={canEdit} />; return <ProductManager canEdit={canEdit} canManage={canManage} />; }

function profileLinksOf(media: Media): ProfileLink[] {
  if (media.profile_links?.length) return media.profile_links;
  return media.website_url ? [{ platform: media.platform_type || '主页', url: media.website_url }] : [];
}

function ProfileLinks({ media }: { media: Media }) {
  const links = profileLinksOf(media);
  return links.length ? <div className="profile-links">{links.map((item, index) => <a key={`${item.url}-${index}`} href={item.url} target="_blank" rel="noreferrer"><span>{item.platform}</span></a>)}</div> : <span className="muted">—</span>;
}

function MediaFormV2({ value, setValue }: { value: any; setValue: (value: any) => void }) {
  const [countries, setCountries] = useState<{ code: string; label: string }[]>([]);
  useEffect(() => { api<any>('/api/options').then((result) => setCountries(result.countries || [])).catch(() => {}); }, []);
  const set = (key: string, next: any) => setValue({ ...value, [key]: next });
  const links: ProfileLink[] = profileLinksOf(value);
  const setLinks = (next: ProfileLink[]) => setValue({ ...value, profile_links: next, website_url: next[0]?.url || '' });
  const isWebsite = value.platform_type === '科技媒体 / 网站';
  return <div className="form-grid">
    <label>名称<Input value={value.name || ''} onChange={(e) => set('name', e.target.value)} /></label>
    <label>国家<SelectField value={value.country || ''} onChange={(country) => set('country', country)} options={countries.map((item) => ({ key: item.label, label: `${item.label} · ${item.code}` }))} placeholder="选择标准国家" /></label>
    <label>渠道<SelectField value={value.platform_type} onChange={(next) => set('platform_type', next)} options={mediaChannelOptions.map((item) => ({ key: item, label: item }))} /></label>
    <label>分类<Input value={value.category || ''} onChange={(e) => set('category', e.target.value)} /></label>
    <div className="wide profile-editor"><div className="section-heading"><div><h3>平台主页</h3><small className="field-hint">每个平台单独维护主页；粉丝或流量统一在下方填写。</small></div><Button icon={<Plus size={14} />} onClick={() => setLinks([...links, { platform: '', url: '' }])}>添加平台</Button></div>
      {links.length ? links.map((item, index) => <div className="profile-link-item" key={index}><div className="profile-link-row profile-link-row-compact"><SelectField value={item.platform} onChange={(platform) => setLinks(links.map((link, i) => i === index ? { ...link, platform } : link))} options={[...mediaChannelOptions.filter((x) => x !== '多平台'), '网站', 'Facebook', 'Twitch', 'Snapchat', 'Media Kit'].map((x) => ({ key: x, label: x }))} placeholder="平台" /><Input value={item.url} onChange={(e) => setLinks(links.map((link, i) => i === index ? { ...link, url: e.target.value } : link))} placeholder="https://..." /><button type="button" className="icon-button danger-text" onClick={() => setLinks(links.filter((_, i) => i !== index))}><Trash2 size={15} /></button></div><div className="profile-link-evidence"><Input value={item.source || ''} onChange={(e) => setLinks(links.map((link, i) => i === index ? { ...link, source: e.target.value } : link))} placeholder="主页来源，例如 Media Kit" /><Input type="date" value={item.verified_at || ''} onChange={(e) => setLinks(links.map((link, i) => i === index ? { ...link, verified_at: e.target.value || undefined } : link))} /><Input type="number" min="0" max="100" value={item.confidence == null ? '' : Math.round(Number(item.confidence) * 100)} onChange={(e) => setLinks(links.map((link, i) => i === index ? { ...link, confidence: e.target.value === '' ? null : Number(e.target.value) / 100 } : link))} placeholder="置信度 %" /></div></div>) : <p className="muted">尚未添加主页，每个平台请单独占一行。</p>}
    </div>
    <label className="media-balanced-field">{isWebsite ? '月访问量（K）' : '粉丝量（K）'}<Input type="number" min="0" step="0.01" value={value.followers_or_traffic ?? ''} onChange={(e) => set('followers_or_traffic', e.target.value ? Number(e.target.value) : null)} /><small className="field-hint">直接填写原始 K 数值，不再换算成等级。</small></label>
    <label className="media-balanced-field">合作状态<SelectField value={value.cooperation_status} onChange={(next) => set('cooperation_status', next)} options={cooperationStatusOptions.map((item) => ({ key: item, label: item }))} placeholder="未联系" /><small className="field-hint field-hint-placeholder" aria-hidden="true">保持字段对齐</small></label>
    <label>数据来源<Input value={value.metric_source || ''} onChange={(e) => set('metric_source', e.target.value)} placeholder="Similarweb、平台官网或人工核验" /></label>
    <label>最近核验<Input type="date" value={value.metric_verified_at || ''} onChange={(e) => set('metric_verified_at', e.target.value || null)} /></label>
    <div className="wide provenance-panel"><div className="section-heading"><div><h3>档案可信度</h3><small className="field-hint">记录整份档案从哪里来；粉丝量或流量仍使用上方的专属来源。</small></div></div><div className="form-grid">
      <label>档案来源<Input value={value.data_source || ''} onChange={(e) => set('data_source', e.target.value)} placeholder="主页、Media Kit、邮件或表格名称" /></label>
      <label>录入方式<SelectField value={value.data_capture_method || 'manual'} onChange={(next) => set('data_capture_method', next)} options={[{ key: 'manual', label: '人工录入' }, { key: 'import', label: '表格导入' }, { key: 'agent', label: 'Agent 提取' }]} /></label>
      <label>置信度（%）<Input type="number" min="0" max="100" value={value.data_confidence == null ? '' : Math.round(Number(value.data_confidence) * 100)} onChange={(e) => set('data_confidence', e.target.value === '' ? null : Number(e.target.value) / 100)} placeholder="人工确认可填 100" /></label>
      <label>档案核验日期<Input type="date" value={value.last_verified_at || ''} onChange={(e) => set('last_verified_at', e.target.value || null)} /></label>
    </div></div>
    <label className="wide">备注<textarea value={value.notes || ''} onChange={(e) => set('notes', e.target.value)} /></label>
  </div>;
}

function MediaManagerV2({ canEdit, canManage }: { canEdit: boolean; canManage: boolean }) {
  const emptyFilters = { country: '', platform_type: '', min_volume: '', max_volume: '', cooperation_status: '' };
  const [items, setItems] = useState<Media[]>([]); const [allMedia, setAllMedia] = useState<Media[]>([]); const [q, setQ] = useState(''); const [filters, setFilters] = useState(emptyFilters); const [filterDraft, setFilterDraft] = useState(emptyFilters); const [filterOpen, setFilterOpen] = useState(false); const [editing, setEditing] = useState<any>(null); const [editingFromReview, setEditingFromReview] = useState(false); const [detailId, setDetailId] = useState<number | null>(null); const [reviewOpen, setReviewOpen] = useState(false); const [reviewCount, setReviewCount] = useState(0);
  const [saving, setSaving] = useState(false);
  const load = (next = filters, query = q) => { const params = new URLSearchParams({ q: query, page_size: '500' }); Object.entries(next).forEach(([key, value]) => value && params.set(key, value)); return api<{ items: Media[] }>(`/api/media?${params}`).then((x) => setItems(x.items)); };
  const refreshAll = () => api<{ items: Media[] }>('/api/media?page_size=500').then((x) => setAllMedia(x.items));
  const refreshReviewCount = () => api<{ total: number }>('/api/media-review-queue').then((x) => setReviewCount(x.total || 0));
  useEffect(() => { void load(); void refreshAll(); void refreshReviewCount(); }, []);
  const options = (key: keyof Media) => [...new Set(allMedia.map((item: any) => item[key]).filter(Boolean))].sort() as string[];
  const save = async () => {
    if (saving) return;
    if (!editing?.name?.trim()) return Notification.error({ message: '请填写媒体名称' });
    const links = profileLinksOf(editing).filter((item) => item.url.trim());
    const invalidLink = links.find((item) => !/^https?:\/\//i.test(item.url));
    if (invalidLink) return Notification.error({ message: '主页地址格式不正确', description: '请填写以 http:// 或 https:// 开头的完整地址。' });
    const payload = { ...editing, name: editing.name.trim(), profile_links: links, website_url: links[0]?.url || null, media_tier: null };
    setSaving(true);
    try {
      await api(editing.id ? `/api/media/${editing.id}` : '/api/media', { method: editing.id ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      setEditing(null);
      await load();
      await refreshAll();
      await refreshReviewCount();
      if (editingFromReview) setReviewOpen(true);
      setEditingFromReview(false);
      Notification.success({ message: '媒体档案已保存' });
    } catch (error) {
      Notification.error({ message: '保存失败', description: String(error) });
    } finally {
      setSaving(false);
    }
  };
  const applyFilters = () => { setFilters(filterDraft); setFilterOpen(false); void load(filterDraft); };
  const formatVolume = (item: Media) => item.followers_or_traffic == null ? '—' : `${item.followers_or_traffic.toLocaleString()} K`;
  return <section><PageHeader title="媒体 / KOL 档案" action={<div className="page-actions"><Button icon={<CheckCircle2 size={16} />} onClick={() => setReviewOpen(true)}>待核验{reviewCount ? ` · ${reviewCount}` : ''}</Button>{canEdit && <Button type="primary" icon={<Plus size={16} />} onClick={() => { setEditingFromReview(false); setEditing({ name: '', country: '', platform_type: '', profile_links: [], category: '', notes: '' }); }}>新建媒体</Button>}<Button icon={<RefreshCw size={16} />} onClick={() => { void load(); void refreshReviewCount(); }}>刷新</Button></div>} />
    <div className="filters media-toolbar"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索媒体、联系人、链接或备注" /><Button onClick={() => void load()}>查询</Button><Popover open={filterOpen} onOpenChange={(open) => { setFilterOpen(open); if (open) setFilterDraft(filters); }} align="end" trigger={<Button icon={<Filter size={16} />}>筛选{Object.values(filters).filter(Boolean).length ? ` · ${Object.values(filters).filter(Boolean).length}` : ''}</Button>}><div className="filter-popover"><header><strong>筛选媒体 / KOL</strong><span>体量统一使用 K</span></header><div className="filter-popover-grid"><label>国家<SelectField value={filterDraft.country} onChange={(country) => setFilterDraft({ ...filterDraft, country })} options={options('country').map((x) => ({ key: x, label: x }))} placeholder="全部国家" /></label><label>渠道<SelectField value={filterDraft.platform_type} onChange={(platform_type) => setFilterDraft({ ...filterDraft, platform_type })} options={options('platform_type').map((x) => ({ key: x, label: x }))} placeholder="全部渠道" /></label><label>最小体量（K）<Input type="number" min="0" value={filterDraft.min_volume} onChange={(e) => setFilterDraft({ ...filterDraft, min_volume: e.target.value })} placeholder="例如 100" /></label><label>最大体量（K）<Input type="number" min="0" value={filterDraft.max_volume} onChange={(e) => setFilterDraft({ ...filterDraft, max_volume: e.target.value })} placeholder="例如 1000" /></label><label>合作状态<SelectField value={filterDraft.cooperation_status} onChange={(cooperation_status) => setFilterDraft({ ...filterDraft, cooperation_status })} options={options('cooperation_status').map((x) => ({ key: x, label: x }))} placeholder="全部状态" /></label></div><footer><Button onClick={() => setFilterDraft(emptyFilters)}>重置</Button><Button type="primary" onClick={applyFilters}>应用</Button></footer></div></Popover></div>
    <DataTable data={items} columns={[{ title: '名称', render: (_: any, r: Media) => <button className="link-button" onClick={() => setDetailId(r.id)}>{r.name}</button>, width: 220 }, { title: '国家', dataIndex: 'country', width: 100 }, { title: '渠道', dataIndex: 'platform_type', width: 120 }, { title: '粉丝 / 流量', render: (_: any, r: Media) => <strong className="volume-cell">{formatVolume(r)}</strong>, width: 140 }, { title: '合作状态', render: (_: any, r: Media) => <StatusTag value={r.cooperation_status || '未联系'} />, width: 110 }, { title: '平台主页', render: (_: any, r: Media) => <ProfileLinks media={r} />, width: 250 }, ...(canEdit ? [{ title: '操作', render: (_: any, r: Media) => <button className="table-action" onClick={() => { setEditingFromReview(false); setEditing({ ...r, profile_links: profileLinksOf(r) }); }}><Pencil size={15} />编辑</button>, width: 90 }] : [])]} />
    {editing && <Dialog title={editing.id ? '编辑媒体' : '新建媒体'} onClose={() => { if (!saving) { setEditing(null); setEditingFromReview(false); } }} onOk={() => void save()} okLabel={saving ? '保存中…' : '保存'}><MediaFormV2 value={editing} setValue={setEditing} /></Dialog>}{detailId && <MediaDetailDrawer mediaId={detailId} canEdit={canEdit} canManage={canManage} onClose={() => setDetailId(null)} onChanged={() => { void load(); void refreshAll(); void refreshReviewCount(); }} />}{reviewOpen && <MediaReviewCenter onClose={() => { setReviewOpen(false); void refreshReviewCount(); void load(); }} onEdit={(media) => { setReviewOpen(false); setEditingFromReview(true); setEditing({ ...media, profile_links: profileLinksOf(media) }); }} onOpenDetail={(mediaId) => { setReviewOpen(false); setDetailId(mediaId); }} />}
  </section>;
}

function MediaManager({ canEdit }: { canEdit: boolean }) {
  const [items, setItems] = useState<any[]>([]); const [allMedia, setAllMedia] = useState<any[]>([]); const [q, setQ] = useState(''); const [filters, setFilters] = useState({ country: '', platform_type: '', media_tier: '', cooperation_status: '' }); const [filterDraft, setFilterDraft] = useState(filters); const [filterOpen, setFilterOpen] = useState(false); const [editing, setEditing] = useState<any>(null); const [detailId, setDetailId] = useState<number | null>(null); const [importOpen, setImportOpen] = useState(false); const [quality, setQuality] = useState<any>(null); const [reviewOpen, setReviewOpen] = useState(false); const [reviewCount, setReviewCount] = useState(0);
  const load = (nextFilters = filters, nextQuery = q) => { const params = new URLSearchParams({ q: nextQuery, page_size: '500' }); Object.entries(nextFilters).forEach(([key, value]) => { if (value) params.set(key, value); }); return api<{ items: any[] }>(`/api/media?${params}`).then((x) => setItems(x.items)); };
  useEffect(() => { void load(); api<{ items: any[] }>('/api/media?page_size=500').then((x) => setAllMedia(x.items)); api<any>('/api/media-review-queue').then((x) => setReviewCount(x.total || 0)); }, []);
  const options = (key: string) => [...new Set(allMedia.map((item) => item[key]).filter(Boolean))].sort();
  const save = async () => { const existing = await api<any>(`/api/media-duplicates?name=${encodeURIComponent(editing.name || '')}&website_url=${encodeURIComponent(editing.website_url || '')}&country=${encodeURIComponent(editing.country || '')}`); if (!editing.id && existing.items.length && !await confirmAction(`发现 ${existing.items.length} 个相同媒体候选，仍要新建吗？`)) return; await api(editing.id ? `/api/media/${editing.id}` : '/api/media', { method: editing.id ? 'PUT' : 'POST', body: JSON.stringify(editing) }); setEditing(null); await load(); api<{ items: any[] }>('/api/media?page_size=500').then((x) => setAllMedia(x.items)); };
  const updateDraft = (key: keyof typeof filters, value: string) => setFilterDraft({ ...filterDraft, [key]: value });
  const appliedCount = Object.values(filters).filter(Boolean).length;
  const openFilters = () => { setFilterDraft(filters); setFilterOpen(true); };
  const applyFilters = () => { setFilters(filterDraft); setFilterOpen(false); void load(filterDraft); };
  const openQuality = async () => { try { const queue = await api<any>('/api/media-review-queue'); setReviewCount(queue.total || 0); setQuality(queue.total ? { review: true } : await api('/api/media-data-quality')); } catch (error) { Notification.error({ message: '读取数据质量报告失败', description: String(error) }); } };
  const applyQuality = async () => { try { const result = await api<any>('/api/media-data-quality/normalize', { method: 'POST' }); Notification.success({ message: `已安全归一 ${result.updated} 条媒体数据`, description: result.needs_review ? `另有 ${result.needs_review} 个字段需要人工核验` : undefined }); setQuality(null); await load(); const all = await api<{ items: any[] }>('/api/media?page_size=500'); setAllMedia(all.items); } catch (error) { Notification.error({ message: '数据归一失败', description: String(error) }); } };
  return <section><PageHeader title="媒体 / KOL 档案" action={<div className="page-actions">{canEdit && <><Button icon={<CheckCircle2 size={16} />} onClick={() => void openQuality()}>整理数据</Button><Button icon={<FileSpreadsheet size={16} />} onClick={() => setImportOpen(true)}>地址导入审核</Button><Button type="primary" icon={<Plus size={16} />} onClick={() => setEditing({ name: '', country: '', platform_type: '', website_url: '', category: '', notes: '' })}>新建媒体</Button></>}<Button icon={<RefreshCw size={16} />} onClick={() => void load()}>刷新</Button></div>} /><div className="filters media-toolbar"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索媒体、联系人、链接或备注" /><Button onClick={() => void load()}>查询</Button><Popover open={filterOpen} onOpenChange={(open) => open ? openFilters() : setFilterOpen(false)} align="end" trigger={<Button icon={<Filter size={16} />}>筛选{appliedCount ? ` · ${appliedCount}` : ""}</Button>}><div className="filter-popover"><header><strong>筛选媒体 / KOL</strong><span>组合条件缩小当前列表</span></header><div className="filter-popover-grid"><label>国家<SelectField value={filterDraft.country} onChange={(value) => updateDraft("country", value)} options={options("country").map((value) => ({ key: value, label: value }))} placeholder="全部国家" /></label><label>渠道<SelectField value={filterDraft.platform_type} onChange={(value) => updateDraft("platform_type", value)} options={options("platform_type").map((value) => ({ key: value, label: value }))} placeholder="全部渠道" /></label><label>媒体等级<SelectField value={filterDraft.media_tier} onChange={(value) => updateDraft("media_tier", value)} options={options("media_tier").map((value) => ({ key: value, label: value }))} placeholder="全部等级" /></label><label>合作状态<SelectField value={filterDraft.cooperation_status} onChange={(value) => updateDraft("cooperation_status", value)} options={options("cooperation_status").map((value) => ({ key: value, label: value }))} placeholder="全部合作状态" /></label></div><footer><Button onClick={() => setFilterDraft({ country: "", platform_type: "", media_tier: "", cooperation_status: "" })}>重置</Button><Button type="primary" onClick={applyFilters}>应用</Button></footer></div></Popover></div><DataTable data={items} columns={[{ title: '名称', render: (_: any, r: any) => <button className="link-button" onClick={() => setDetailId(r.id)}>{r.name}</button>, width: 230 }, { title: '国家', dataIndex: 'country', width: 110 }, { title: '渠道', dataIndex: 'platform_type', width: 130 }, { title: '等级', render: (_: any, r: any) => <span className="tier-cell"><span className="tier-badge">{r.media_tier || '—'}</span></span>, width: 90 }, { title: '合作状态', render: (_: any, r: any) => <StatusTag value={r.cooperation_status || '未联系'} />, width: 110 }, { title: '主页', render: (_: any, r: Media) => r.website_url ? <a href={r.website_url} target="_blank">打开主页</a> : '-' }, { title: '档案', render: (_: any, r: any) => <button className="table-action" onClick={() => setDetailId(r.id)}>查看联系人与地址</button>, width: 180 }, ...(canEdit ? [{ title: '操作', render: (_: any, r: any) => <button className="table-action" onClick={() => setEditing({ ...r })}><Pencil size={15} />编辑</button>, width: 90 }] : [])]} />{editing && <Dialog title={editing.id ? '编辑媒体' : '新建媒体'} onClose={() => setEditing(null)} onOk={() => void save()}><MediaForm value={editing} setValue={setEditing} /></Dialog>}{detailId && <MediaDetailDrawer mediaId={detailId} canEdit={canEdit} onClose={() => setDetailId(null)} onChanged={() => void load()} />}{importOpen && <AddressImportReview onClose={() => setImportOpen(false)} />}{quality && <DataQualityDialog report={quality} onClose={() => setQuality(null)} onApply={() => void applyQuality()} />}</section>;
}

function DataQualityDialog({ report, onClose, onApply }: { report: any; onClose: () => void; onApply: () => void }) {
  const changes = report.items || [];
  if (report.review) return <MediaReviewCenter onClose={onClose} />;
  return <Dialog variant="modal" title="媒体数据整理" onClose={onClose} onOk={changes.length ? onApply : undefined} okLabel="应用安全归一"><p className="muted">只自动处理确定性高的渠道别名、合作状态同义词，以及可由粉丝量计算的空白等级；无法判断的原始内容不会被覆盖。</p><div className="quality-summary"><div><span>可安全归一</span><strong>{report.safe_changes || 0}</strong></div><div><span>待人工核验</span><strong>{report.needs_review || 0}</strong></div><div><span>当前媒体</span><strong>{report.total || 0}</strong></div></div>{changes.length ? <div className="quality-list">{changes.slice(0, 30).map((item: any) => <div className="quality-row" key={item.id}><strong>{item.name}</strong><span>{item.changes.join(' · ')}</span></div>)}</div> : <p className="muted">没有发现可自动归一的数据。</p>}{report.needs_review > 0 && <p className="field-hint">有 {report.needs_review} 个字段无法可靠判断，将保留原值，等待人工确认。</p>}</Dialog>;
}

function MediaReviewCenter({ onClose, onEdit, onOpenDetail }: { onClose: () => void; onEdit?: (media: Media) => void; onOpenDetail?: (mediaId: number) => void }) {
  const [report, setReport] = useState<any>({ items: [], total: 0, category_counts: {} }); const [category, setCategory] = useState(''); const [selected, setSelected] = useState<Set<number>>(new Set());
  const load = () => api<any>('/api/media-review-queue').then(setReport);
  useEffect(() => { void load(); }, []);
  const editMedia = async (mediaId: number) => { try { const detail = await api<any>(`/api/media/${mediaId}`); onEdit?.(detail.media); } catch (error) { Notification.error({ message: '读取媒体档案失败', description: String(error) }); } };
  const complete = async (item: any) => { if (!await confirmAction(`确认“${item.name}”的资料问题已处理完成？`)) return; try { await api(`/api/media-review-queue/${item.id}/resolve`, { method: 'POST', body: JSON.stringify({}) }); await load(); Notification.success({ message: '已移出待核验队列' }); } catch (error) { Notification.error({ message: '暂时无法完成核验', description: String(error) }); } };
  const runBatch = async (action: 'resolve' | 'snooze') => { if (!selected.size) return; try { const result = await api<any>('/api/media-review-queue/batch', { method: 'POST', body: JSON.stringify({ media_ids: [...selected], action, snooze_days: 30 }) }); setSelected(new Set()); await load(); Notification.success({ message: action === 'snooze' ? `已将 ${result.changed} 条延后 30 天` : `已确认 ${result.changed} 条`, description: result.skipped?.length ? `${result.skipped.length} 条仍有必须先处理的问题` : undefined }); } catch (error) { Notification.error({ message: '批量处理失败', description: String(error) }); } };
  const items = report.items || []; const visibleItems = category ? items.filter((item: any) => item.categories?.includes(category)) : items.filter((item: any) => item.priority); const counts = report.category_counts || {};
  const filters = [{ key: '', label: '优先处理', count: report.total || 0 }, { key: 'duplicate', label: '疑似重复', count: counts.duplicate || 0 }, { key: 'contact', label: '缺联系方式', count: counts.contact || 0 }, { key: 'profile', label: '主页异常', count: counts.profile || 0 }, { key: 'source', label: '来源补录', count: counts.source || 0 }, { key: 'stale', label: '长期未核验', count: counts.stale || 0 }, { key: 'conflict', label: '资料冲突', count: counts.conflict || 0 }, { key: 'confidence', label: '低置信度', count: counts.confidence || 0 }];
  return <Dialog title={`待核验中心 · ${report.total || 0}`} onClose={onClose}><div className="review-intro"><strong>按问题处理，而不是逐条盲目确认</strong><span>默认只计算需要立即处理的档案；{report.maintenance_total || 0} 条历史来源补录单独维护，不制造红色噪声。</span></div><div className="review-filters">{filters.map((option) => <button type="button" key={option.key} className={category === option.key ? 'active' : ''} onClick={() => { setCategory(option.key); setSelected(new Set()); }}>{option.label}<span>{option.count}</span></button>)}</div>{visibleItems.length ? <><div className="review-batch-bar"><label><input type="checkbox" checked={visibleItems.length > 0 && visibleItems.every((item: any) => selected.has(item.id))} onChange={(event) => setSelected(event.target.checked ? new Set(visibleItems.map((item: any) => item.id)) : new Set())} />选择当前分类</label><span>已选 {selected.size} 条</span><Button size="sm" disabled={!selected.size} onClick={() => void runBatch('snooze')}>稍后 30 天</Button><Button size="sm" disabled={!selected.size} onClick={() => void runBatch('resolve')}>批量确认</Button></div><div className="review-list">{visibleItems.map((item: any) => { const missingContact = item.issue_codes?.includes('missing_contact'); const duplicate = item.issue_codes?.includes('possible_duplicate'); const mustEdit = item.issue_codes?.some((code: string) => ['missing_source', 'stale_metric', 'low_confidence', 'data_conflict'].includes(code)); const canComplete = !missingContact && !duplicate && !mustEdit; const displayedIssues = category ? item.issues : item.issues?.filter((issue: any) => ['duplicate', 'contact', 'profile', 'conflict', 'confidence'].includes(issue.category)); return <article className="review-row" key={item.id}><input className="review-checkbox" type="checkbox" checked={selected.has(item.id)} onChange={() => setSelected((current) => { const next = new Set(current); next.has(item.id) ? next.delete(item.id) : next.add(item.id); return next; })} /><div className="review-main"><div className="review-title-line"><strong>{item.name}</strong><span>{[item.country, item.platform_type].filter(Boolean).join(' · ') || '未补充基础资料'}</span></div><div className="review-issue-tags">{displayedIssues?.map((issue: any) => <span key={issue.code}>{issue.label}</span>)}</div><p>{displayedIssues?.map((issue: any) => issue.reason).join('；')}</p></div><div className="review-actions">{onOpenDetail && duplicate && <Button size="sm" type="primary" icon={<GitMerge size={14} />} onClick={() => onOpenDetail(item.id)}>核对并合并</Button>}{onOpenDetail && missingContact && <Button size="sm" type="primary" icon={<UserPlus size={14} />} onClick={() => onOpenDetail(item.id)}>补充联系方式</Button>}{onEdit && !duplicate && !missingContact && <Button size="sm" icon={<Pencil size={14} />} onClick={() => void editMedia(item.id)}>编辑资料</Button>}{canComplete && <Button size="sm" icon={<CheckCircle2 size={14} />} onClick={() => void complete(item)}>标记已处理</Button>}</div></article>; })}</div></> : <div className="review-complete"><CheckCircle2 size={30} /><strong>{items.length ? '当前分类已处理完成' : '待核验任务已全部处理'}</strong><span>{items.length ? '可以切换其他分类继续检查。' : '这里只展示有明确处理理由的数据。'}</span></div>}</Dialog>;
}

function MediaDetailDrawer({ mediaId, canEdit, canManage = false, onClose, onChanged }: { mediaId: number; canEdit: boolean; canManage?: boolean; onClose: () => void; onChanged: () => void }) {
  const [data, setData] = useState<any>(null); const [contact, setContact] = useState<any>(null); const [address, setAddress] = useState<any>(null); const [merging, setMerging] = useState(false); const [targetMediaId, setTargetMediaId] = useState<number | null>(null); const [mediaOptions, setMediaOptions] = useState<Media[]>([]); const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const load = async () => { try { const detail = await api<any>(`/api/media/${mediaId}`); setData(detail); if (canEdit) { const history = await api<any>(`/api/audit-logs?entity_type=media&entity_id=${mediaId}&limit=20`); setAuditLogs(history.items || []); } } catch (error) { Notification.error({ message: '读取媒体档案失败', description: String(error) }); } }; useEffect(() => { void load(); }, [mediaId]);
  const removeContact = async (item: any) => { if (!await confirmAction(`删除联系人“${item.name || '未命名'}”？关联地址会保留在媒体档案中。`)) return; await api(`/api/contacts/${item.id}`, { method: 'DELETE' }); await load(); };
  const removeAddress = async (item: ShippingAddress) => { if (!await confirmAction('删除这条地址档案？历史寄样快照不会受影响。')) return; await api(`/api/shipping-addresses/${item.id}`, { method: 'DELETE' }); await load(); };
  const makeDefault = async (item: ShippingAddress) => { await api(`/api/shipping-addresses/${item.id}/default`, { method: 'POST' }); await load(); };
  if (!data) return <Dialog title="媒体档案" onClose={onClose}><div className="loading-state">正在读取档案...</div></Dialog>;
  const media = data.media; const contacts = data.contacts || []; const addresses: ShippingAddress[] = data.shipping_addresses || []; const campaigns = data.campaigns || []; const links = profileLinksOf(media); const products = data.products || [];
  const beginMerge = async () => { const result = await api<{ items: Media[] }>('/api/media?page_size=500'); setMediaOptions(result.items.filter((item) => item.id !== media.id)); setTargetMediaId(null); setMerging(true); };
  const merge = async () => { if (!targetMediaId) return Notification.error({ message: '请选择保留的目标媒体' }); const target = mediaOptions.find((item) => item.id === targetMediaId); if (!target) return; try { const preview = await api<any>(`/api/media/${media.id}/merge-preview?target_media_id=${targetMediaId}`); const conflicts = preview.field_conflicts?.length ? `\n${preview.field_conflicts.length} 个字段有差异，将保留目标媒体的值。` : ''; if (!await confirmAction(`将“${media.name}”合并到“${target.name}”？\n\n将转移 ${preview.moves.campaigns} 条合作、${preview.moves.contacts} 个联系人、${preview.moves.addresses} 条地址；${preview.moves.duplicate_contacts} 个重复联系人会合并。${conflicts}\n当前错误媒体随后删除。`)) return; const result = await api<any>(`/api/media/${media.id}/merge`, { method: 'POST', body: JSON.stringify({ target_media_id: targetMediaId }) }); Notification.success({ message: `已合并到 ${target.name}`, description: `转移 ${result.campaigns} 条合作记录、${result.contacts} 个联系人和 ${result.addresses} 条地址` }); setMerging(false); onChanged(); onClose(); } catch (error) { Notification.error({ message: '合并失败', description: String(error) }); } };
  const removeMedia = async () => { if (!await confirmAction(`永久删除媒体“${media.name}”？\n\n只有没有联系人、地址和合作记录的媒体可以删除；有关联数据时请使用“合并媒体”。`)) return; try { await api(`/api/media/${media.id}`, { method: 'DELETE' }); Notification.success({ message: '媒体已永久删除' }); onChanged(); onClose(); } catch (error) { Notification.error({ message: '无法删除媒体', description: String(error) }); } };
  const restoreAudit = async (log: any) => { if (!await confirmAction(`将媒体资料恢复到 ${formatDateTime(log.created_at)} 修改前的版本？\n\n本次恢复也会写入修改记录。`)) return; try { await api(`/api/audit-logs/${log.id}/restore`, { method: 'POST' }); await load(); onChanged(); Notification.success({ message: '已恢复到修改前版本' }); } catch (error) { Notification.error({ message: '恢复失败', description: String(error) }); } };
  const management = canManage ? <Popover align="start" trigger={<Button icon={<MoreHorizontal size={16} />}>更多操作</Button>}><div className="record-action-menu"><button onClick={() => void beginMerge()}>合并媒体<span>把历史数据转移到正确媒体</span></button><button className="record-action-menu-danger" onClick={() => void removeMedia()}>永久删除<span>仅允许删除无关联数据的媒体</span></button></div></Popover> : undefined;
  return <Dialog title={media.name} onClose={onClose} footerStart={management}><div className="media-detail media-360"><div className="media-hero"><div><div className="media-hero-title"><strong>{media.name}</strong><StatusTag value={media.cooperation_status || '未联系'} /></div><p>{[media.country, media.platform_type, media.category].filter(Boolean).join(' · ') || '基础资料待补充'}</p><span>{media.notes || '暂无媒体备注'}</span></div><div className="metric-card"><small>{media.audience_metric_type === 'monthly_visits' || media.platform_type === '科技媒体 / 网站' ? '月访问量' : '粉丝 / 流量'}</small><strong>{media.followers_or_traffic != null ? `${Number(media.followers_or_traffic).toLocaleString()} K` : '待补充'}</strong><span>{media.metric_source || '未记录数据来源'} · {media.metric_verified_at || '未核验'}</span></div></div><div className="media-kpis"><div><strong>{links.length}</strong><span>平台主页</span></div><div><strong>{contacts.length}</strong><span>联系人</span></div><div><strong>{addresses.length}</strong><span>收件地址</span></div><div><strong>{campaigns.length}</strong><span>合作记录</span></div><div><strong>{products.length}</strong><span>关联产品</span></div></div>
    <div className="section-heading"><div><h3>平台主页</h3><small className="field-hint">每个平台保持独立入口，避免账号与数据混在一起</small></div></div>{links.length ? <div className="platform-grid">{links.map((item, index) => <a href={item.url} target="_blank" rel="noreferrer" key={`${item.url}-${index}`}><span>{item.platform || '主页'}</span><strong>打开主页 ↗</strong><small>{item.url.replace(/^https?:\/\//, '').slice(0, 48)}</small></a>)}</div> : <p className="muted">尚未登记平台主页</p>}
    <div className="section-heading"><h3>联系人</h3>{canEdit && <Button icon={<UserPlus size={15} />} onClick={() => setContact({ media_id: media.id, name: '', role: '', email: '', phone: '' })}>新增联系人</Button>}</div>{contacts.length ? <div className="record-list">{contacts.map((item: any) => <div className="record-row" key={item.id}><div><strong>{item.name || '未命名'}{item.is_primary ? ' · 主联系人' : ''}</strong><span>{[item.role, item.email, item.phone].filter(Boolean).join(' · ') || '暂无联系方式'}</span></div>{canEdit && <div className="row-actions"><button className="table-action" onClick={() => setContact(item)}><Pencil size={14} />编辑</button><button className="table-action danger-text" onClick={() => void removeContact(item)}><Trash2 size={14} />删除</button></div>}</div>)}</div> : <p className="muted">尚未登记联系人</p>}
    <div className="section-heading"><h3>收件地址</h3>{canEdit && <Button icon={<Plus size={15} />} onClick={() => setAddress({ media_id: media.id, contact_id: null, address_text: '', country: media.country || '', is_default: !addresses.length, is_confirmed: true })}>新增地址</Button>}</div>{addresses.length ? <div className="address-list">{addresses.map((item) => <article className="address-card" key={item.id}><header><strong>{item.recipient_name || '未填写收件人'}</strong>{item.is_default && <Tag color="app-teal">默认地址</Tag>}</header><p>{item.address_text}</p><small>{[item.phone, item.email, item.city, item.region, item.postal_code, item.country].filter(Boolean).join(' · ')}</small><div className="row-actions"><button className="table-action" onClick={() => void navigator.clipboard.writeText(formatAddress(item))}>复制</button>{canEdit && <><button className="table-action" onClick={() => setAddress(item)}>编辑</button>{!item.is_default && <button className="table-action" onClick={() => void makeDefault(item)}>设为默认</button>}<button className="table-action danger-text" onClick={() => void removeAddress(item)}>删除</button></>}</div></article>)}</div> : <p className="muted">尚未登记收件地址</p>}
    <div className="section-heading"><div><h3>关联产品与合作历史</h3><small className="field-hint">按最近更新排序，保留项目、负责人、下一步和动态</small></div></div>{products.length > 0 && <div className="related-products">{products.map((item: any) => <Tag key={item.id} color="app-teal">{item.model}</Tag>)}</div>}{campaigns.length ? <div className="campaign-history">{campaigns.map((item: any) => <article key={item.id}><header><div><strong>{item.project?.name || '未归属项目'}</strong><span>{item.product?.model || item.collaboration_type || '未关联产品'}</span></div><StatusTag value={item.execution_status} /></header><div className="campaign-history-meta"><span>负责人：{item.owner?.name || '未分配'}</span><span>下一步：{item.next_action || nextActionByStatus[item.execution_status] || '待补充'}</span><span>跟进：{item.follow_up_date || '未设置'}</span></div>{item.activities?.slice(0, 2).map((activity: any) => <p key={activity.id}><strong>{activity.activity_type}</strong> {activity.content} <small>{formatDateTime(activity.created_at)}</small></p>)}</article>)}</div> : <p className="muted">尚无合作执行记录</p>}
    <div className="section-heading"><div><h3>资料来源与修改记录</h3><small className="field-hint">{media.data_source || '未记录来源'} · {media.data_capture_method === 'agent' ? 'Agent 提取' : media.data_capture_method === 'import' ? '表格导入' : '人工录入'} · {media.last_verified_at || '尚未核验'}</small></div></div>{auditLogs.length ? <div className="audit-list">{auditLogs.slice(0, 8).map((log: any) => <article key={log.id}><div><strong>{log.action === 'update' ? '更新媒体资料' : log.action === 'restore' ? '恢复历史版本' : log.action === 'merge' ? '合并媒体' : log.action}</strong><span>{log.user || '系统'} · {formatDateTime(log.created_at)}{log.reason ? ` · ${log.reason}` : ''}</span></div>{canManage && ['update', 'restore'].includes(log.action) && <Button size="sm" onClick={() => void restoreAudit(log)}>恢复此版本</Button>}</article>)}</div> : <p className="muted">暂无修改记录</p>}
  </div>{contact && <ContactDrawer value={contact} onClose={() => setContact(null)} onSaved={() => { setContact(null); void load(); onChanged(); }} />}{address && <AddressDrawer value={address} contacts={contacts} onClose={() => setAddress(null)} onSaved={() => { setAddress(null); void load(); }} />}{merging && <Dialog variant="modal" title={`合并媒体 · ${media.name}`} onClose={() => setMerging(false)} onOk={() => void merge()} okLabel="确认合并"><div className="form-grid"><label className="wide">保留为<EntityLookup value={targetMediaId} onChange={setTargetMediaId} options={mediaOptions.map((item) => ({ id: item.id, label: item.name, search: `${item.name} ${item.country || ''} ${item.platform_type || ''} ${item.website_url || ''}` }))} placeholder="搜索正确的媒体名称或主页" /></label><p className="wide merge-warning">当前媒体的联系人、地址和全部合作历史会转移到目标媒体；当前媒体随后删除。目标媒体已有资料优先保留。</p></div></Dialog>}</Dialog>;
}

function formatAddress(item: Partial<ShippingAddress>) { return [item.recipient_name, item.phone, item.email, item.address_text, [item.city, item.region, item.postal_code, item.country].filter(Boolean).join(' '), item.tax_or_customs_number ? `税号/清关号: ${item.tax_or_customs_number}` : '', item.shipping_notes].filter(Boolean).join('\n'); }

function AddressDrawer({ value, contacts, onClose, onSaved }: { value: any; contacts: any[]; onClose: () => void; onSaved: () => void }) { const [form, setForm] = useState(value); const set = (key: string, next: any) => setForm({ ...form, [key]: next }); const save = async () => { if (!form.address_text?.trim()) return Notification.error({ message: '请填写完整地址' }); await api(form.id ? `/api/shipping-addresses/${form.id}` : '/api/shipping-addresses', { method: form.id ? 'PUT' : 'POST', body: JSON.stringify({ ...form, address_text: form.address_text.trim() }) }); onSaved(); }; return <Dialog title={form.id ? '编辑收件地址' : '新增收件地址'} onClose={onClose} onOk={() => void save()}><div className="form-grid"><label>关联联系人<SelectField value={form.contact_id || ''} onChange={(x) => set('contact_id', x ? Number(x) : null)} options={contacts.map((item) => ({ key: String(item.id), label: item.name || `联系人 ${item.id}` }))} placeholder="不指定联系人" /></label><label>收件人<Input value={form.recipient_name || ''} onChange={(e) => set('recipient_name', e.target.value)} /></label><label>电话<Input value={form.phone || ''} onChange={(e) => set('phone', e.target.value)} /></label><label>邮箱<Input value={form.email || ''} onChange={(e) => set('email', e.target.value)} /></label><label className="wide">完整地址<textarea value={form.address_text || ''} onChange={(e) => set('address_text', e.target.value)} /></label><label>城市<Input value={form.city || ''} onChange={(e) => set('city', e.target.value)} /></label><label>省 / 州<Input value={form.region || ''} onChange={(e) => set('region', e.target.value)} /></label><label>邮编<Input value={form.postal_code || ''} onChange={(e) => set('postal_code', e.target.value)} /></label><label>国家<Input value={form.country || ''} onChange={(e) => set('country', e.target.value)} /></label><label className="wide">税号 / 清关号<Input value={form.tax_or_customs_number || ''} onChange={(e) => set('tax_or_customs_number', e.target.value)} /></label><label className="wide">寄送说明<textarea value={form.shipping_notes || ''} onChange={(e) => set('shipping_notes', e.target.value)} /></label><label className="wide">原始文本<textarea value={form.source_text || ''} onChange={(e) => set('source_text', e.target.value)} /></label><label className="checkbox-label"><input type="checkbox" checked={Boolean(form.is_default)} onChange={(e) => set('is_default', e.target.checked)} />设为该媒体默认地址</label></div></Dialog>; }

function AddressImportReview({ onClose }: { onClose: () => void }) { const [items, setItems] = useState<any[]>([]); const [sourceAvailable, setSourceAvailable] = useState(true); const [editing, setEditing] = useState<any>(null); useEffect(() => { api<any>('/api/address-import/candidates').then((result) => { setItems(result.items || []); setSourceAvailable(result.source_available); }); }, []); const pending = items.filter((item) => !item.imported); return <Dialog title="历史地址导入审核" onClose={onClose}><div className="review-note">候选不会自动写入地址库。请逐条确认媒体、联系人和地址字段。</div>{!sourceAvailable ? <p className="muted">本机未找到历史清洗文件，可直接在媒体详情中新增地址。</p> : pending.length ? <div className="review-list">{pending.map((item) => <div className="review-row" key={item.id}><div><strong>{item.media_name || '未匹配媒体'}</strong><span>{item.contact_name || '未匹配联系人'}</span><p>{item.raw_text}</p></div><Button disabled={!item.media_id} onClick={() => setEditing({ ...item.parsed, media_id: item.media_id, contact_id: item.contact_id, is_default: false })}>{item.media_id ? '审核导入' : '请先匹配媒体'}</Button></div>)}</div> : <p className="muted">没有待审核的地址候选</p>}{editing && <AddressDrawer value={editing} contacts={[]} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); api<any>('/api/address-import/candidates').then((result) => setItems(result.items || [])); }} />}</Dialog>; }

function ContactManager({ canEdit }: { canEdit: boolean }) { const [items, setItems] = useState<any[]>([]); const [q, setQ] = useState(''); const [editing, setEditing] = useState<any>(null); const load = () => api<{ items: any[] }>(`/api/contacts?q=${encodeURIComponent(q)}&page_size=300`).then((x) => setItems(x.items)); useEffect(() => { void load(); }, []); return <section><PageHeader title="联系人" action={<div className="page-actions">{canEdit && <Button type="primary" icon={<Plus size={16} />} onClick={() => setEditing({ name: '', role: '', email: '', phone: '', media_id: null, media_label: '' })}>新建联系人</Button>}<Button icon={<RefreshCw size={16} />} onClick={load}>刷新</Button></div>} /><div className="filters"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索姓名、邮箱或媒体" /><Button onClick={load}>查询</Button></div><DataTable data={items} columns={[{ title: '媒体', render: (_: any, r: any) => r.media?.name || '-', width: 180 }, { title: '姓名', render: (_: any, r: any) => canEdit ? <button className="link-button" onClick={() => setEditing({ ...r, media_label: r.media ? `${r.media.name}${r.media.country ? ` · ${r.media.country}` : ''}` : '' })}>{r.name || '未命名'}</button> : (r.name || '未命名'), width: 160 }, { title: '职位', dataIndex: 'role', width: 150 }, { title: '邮箱', dataIndex: 'email', width: 240 }, { title: '电话', dataIndex: 'phone', width: 170 }]} />{editing && <ContactDrawer value={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load(); }} />}</section>; }

function MediaForm({ value, setValue }: { value: any; setValue: (value: any) => void }) {
  const set = (key: string, next: any) => setValue({ ...value, [key]: next });
  const isWebsite = value.platform_type === '科技媒体 / 网站';
  const metricLabel = isWebsite ? '月访问量（K）' : '粉丝量（K）';
  return <div className="form-grid"><label>名称<Input value={value.name || ''} onChange={(e) => set('name', e.target.value)} /></label><label>国家<Input value={value.country || ''} onChange={(e) => set('country', e.target.value)} /></label><label>渠道<SelectField value={value.platform_type} onChange={(next) => set('platform_type', next)} options={mediaChannelOptions.map((item) => ({ key: item, label: item }))} /></label><label>分类<Input value={value.category || ''} onChange={(e) => set('category', e.target.value)} /></label><label className="wide">主页链接<Input value={value.website_url || ''} onChange={(e) => set('website_url', e.target.value)} /></label><label>{metricLabel}<Input type="number" min="0" step="0.01" value={value.followers_or_traffic ?? ''} onChange={(e) => set('followers_or_traffic', e.target.value ? Number(e.target.value) : null)} /><small className="field-hint">{isWebsite ? '填写估算月访问量，例如 96460 表示 9,646 万次/月。' : '填写粉丝数，例如 15700 表示 1,570 万粉丝。'}</small></label><label>媒体等级<SelectField value={value.media_tier} onChange={(next) => set('media_tier', next)} options={mediaTierOptions.map((item) => ({ key: item, label: item }))} placeholder="按指标自动评估" /><small className="field-hint">统一按 K 计算：S ≥ 1000、A ≥ 500、B ≥ 100、C ≥ 10、D &lt; 10。</small></label><label>合作状态<SelectField value={value.cooperation_status} onChange={(next) => set('cooperation_status', next)} options={cooperationStatusOptions.map((item) => ({ key: item, label: item }))} placeholder="未联系" /></label><label className="wide">备注<textarea value={value.notes || ''} onChange={(e) => set('notes', e.target.value)} /></label></div>;
}

function ContactDrawer({ value, onClose, onSaved }: { value: any; onClose: () => void; onSaved: () => void }) { const [form, setForm] = useState(value); const [media, setMedia] = useState<Media[]>([]); const [quickMedia, setQuickMedia] = useState<any>(null); useEffect(() => { api<{ items: Media[] }>('/api/media?page_size=500').then((x) => setMedia(x.items)); }, []); const save = async () => { if (!form.media_id) return Notification.error({ message: '请先选择或新建挂靠媒体' }); await api(form.id ? `/api/contacts/${form.id}` : '/api/contacts', { method: form.id ? 'PUT' : 'POST', body: JSON.stringify({ ...form, media_id: form.media_id }) }); onSaved(); }; const saveQuickMedia = async () => { const created = await api<any>('/api/media', { method: 'POST', body: JSON.stringify(quickMedia) }); setMedia([...media, created]); setForm({ ...form, media_id: created.id }); setQuickMedia(null); }; return <><Dialog title={form.id ? '编辑联系人' : '新建联系人'} onClose={onClose} onOk={() => void save()}><div className="form-grid"><label className="wide">挂靠媒体 / KOL<EntityLookup value={form.media_id} onChange={(mediaId) => setForm({ ...form, media_id: mediaId })} options={mediaLookupOptions(media)} placeholder="输入媒体名称、国家、渠道或主页链接" /><button type="button" className="link-button" onClick={() => setQuickMedia({ name: '', country: '', platform_type: '', website_url: '' })}>没有对应媒体？新建媒体</button></label><label>姓名<Input value={form.name || ''} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><label>职位<Input value={form.role || ''} onChange={(e) => setForm({ ...form, role: e.target.value })} /></label><label>Email<Input value={form.email || ''} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label><label>电话<Input value={form.phone || ''} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label><label>WhatsApp<Input value={form.whatsapp || ''} onChange={(e) => setForm({ ...form, whatsapp: e.target.value })} /></label><label>Telegram<Input value={form.telegram || ''} onChange={(e) => setForm({ ...form, telegram: e.target.value })} /></label><label>Brief 邮箱<Input value={form.brief_email || ''} onChange={(e) => setForm({ ...form, brief_email: e.target.value })} /></label><label>PR 邮箱<Input value={form.press_release_email || ''} onChange={(e) => setForm({ ...form, press_release_email: e.target.value })} /></label><label>信息来源<Input value={form.data_source || ''} onChange={(e) => setForm({ ...form, data_source: e.target.value })} placeholder="邮件签名、Media Kit 或人工确认" /></label><label>录入方式<SelectField value={form.data_capture_method || 'manual'} onChange={(data_capture_method) => setForm({ ...form, data_capture_method })} options={[{ key: 'manual', label: '人工录入' }, { key: 'import', label: '表格导入' }, { key: 'agent', label: 'Agent 提取' }]} /></label><label>置信度（%）<Input type="number" min="0" max="100" value={form.data_confidence == null ? '' : Math.round(Number(form.data_confidence) * 100)} onChange={(e) => setForm({ ...form, data_confidence: e.target.value === '' ? null : Number(e.target.value) / 100 })} /></label><label>核验日期<Input type="date" value={form.verified_at || ''} onChange={(e) => setForm({ ...form, verified_at: e.target.value || null })} /></label><label className="wide">备注<textarea value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label></div></Dialog>{quickMedia && <Dialog variant="modal" title="新建挂靠媒体" onClose={() => setQuickMedia(null)} onOk={() => void saveQuickMedia()}><MediaForm value={quickMedia} setValue={setQuickMedia} /></Dialog>}</>; }

const agentFieldLabels: Record<string, string> = {
  name: '媒体名称', country: '国家 / 地区', platform_type: '渠道', category: '媒体分类', profile_links: '平台主页',
  followers_or_traffic: '粉丝 / 流量（K）', audience_metric_type: '体量口径', metric_source: '指标来源', metric_verified_at: '指标核验日期', cooperation_status: '合作状态', notes: '档案备注',
  role: '联系人职位', email: '联系人邮箱', phone: '联系人电话', whatsapp: 'WhatsApp', telegram: 'Telegram',
};

function AgentWorkspace({ canEdit, canManage }: { canEdit: boolean; canManage: boolean }) {
  const [status, setStatus] = useState<any>(null); const [runs, setRuns] = useState<AgentRun[]>([]); const [media, setMedia] = useState<Media[]>([]); const [inputType, setInputType] = useState<'url' | 'text'>('url'); const [content, setContent] = useState(''); const [sourceLabel, setSourceLabel] = useState(''); const [working, setWorking] = useState(false); const [testingProvider, setTestingProvider] = useState<string | null>(null); const [active, setActive] = useState<AgentRun | null>(null); const [selected, setSelected] = useState<Set<string>>(new Set()); const [targetMediaId, setTargetMediaId] = useState<number | null>(null); const [createMedia, setCreateMedia] = useState(false);
  const load = async () => { const [config, history, mediaRows] = await Promise.all([api<any>('/api/agent/status'), api<{ items: AgentRun[] }>('/api/agent/runs'), api<{ items: Media[] }>('/api/media?page_size=500')]); setStatus(config); setRuns(history.items); setMedia(mediaRows.items); };
  useEffect(() => { void load(); }, []);
  const proposalFields = (run: AgentRun) => { const proposal = run.proposal || {}; const rows: Array<{ path: string; label: string; value: any; evidence?: string; confidence: number }> = []; Object.entries(proposal.media || {}).forEach(([key, value]) => { if (value == null || value === '' || (Array.isArray(value) && !value.length)) return; const path = `media.${key}`; rows.push({ path, label: agentFieldLabels[key] || key, value, evidence: proposal.evidence?.[path], confidence: Number(proposal.confidence?.[path] ?? .49) }); }); (proposal.contacts || []).forEach((contact: any, index: number) => Object.entries(contact).forEach(([key, value]) => { if (value == null || value === '') return; const path = `contacts.${index}.${key}`; rows.push({ path, label: `${index + 1} 号联系人 · ${agentFieldLabels[key] || (key === 'name' ? '姓名' : key)}`, value, evidence: proposal.evidence?.[path], confidence: Number(proposal.confidence?.[path] ?? .49) }); })); return rows; };
  const openRun = (run: AgentRun) => { setActive(run); const rows = proposalFields(run); setSelected(new Set(rows.filter((row) => row.confidence >= .8 && row.evidence).map((row) => row.path))); const suggested = run.proposal?.suggested_target_media_id || run.target_media_id || null; setTargetMediaId(suggested); setCreateMedia(!suggested); };
  const extract = async () => { if (!canEdit || working) return; setWorking(true); try { const run = await api<AgentRun>('/api/agent/extract', { method: 'POST', body: JSON.stringify({ input_type: inputType, content, source_label: sourceLabel || null }) }); setContent(''); setSourceLabel(''); await load(); openRun(run); Notification.success({ message: 'Agent 已生成字段建议', description: '高置信度字段已预选，仍需你确认后才会写入。' }); } catch (error) { Notification.error({ message: 'Agent 提取失败', description: String(error) }); } finally { setWorking(false); } };
  const apply = async () => { if (!active || !selected.size) return; setWorking(true); try { const result = await api<any>(`/api/agent/runs/${active.id}/apply`, { method: 'POST', body: JSON.stringify({ selected_fields: [...selected], target_media_id: createMedia ? null : targetMediaId, create_media: createMedia }) }); setActive(null); await load(); Notification.success({ message: `已写入 ${result.media.name}`, description: result.contacts_created ? `同时创建 ${result.contacts_created} 个联系人` : '本次未创建联系人' }); } catch (error) { Notification.error({ message: '写入失败', description: String(error) }); } finally { setWorking(false); } };
  const reject = async () => { if (!active || !await confirmAction('拒绝这份 Agent 建议？记录会保留，但不会写入任何媒体资料。')) return; await api(`/api/agent/runs/${active.id}/reject`, { method: 'POST', body: JSON.stringify({ reason: '人工核对后不采用' }) }); setActive(null); await load(); };
  const testConnection = async (provider: 'deepseek' | 'youtube') => { if (!canManage || testingProvider) return; setTestingProvider(provider); try { const result = await api<any>(`/api/integrations/${provider}/test`, { method: 'POST' }); await load(); result.ok ? Notification.success({ message: '连接测试成功', description: result.message }) : Notification.error({ message: '连接测试失败', description: result.message }); } catch (error) { Notification.error({ message: '连接测试失败', description: String(error) }); } finally { setTestingProvider(null); } };
  const connectionLabel = (configured: boolean, lastTest: any) => !configured ? '未连接' : lastTest?.status === 'connected' ? '已连接' : lastTest?.status === 'failed' ? '连接异常' : '待测试';
  const formatAgentValue = (value: any) => Array.isArray(value) ? value.map((item) => item.url || item.name || JSON.stringify(item)).join('；') : String(value);
  return <section className="resource-page agent-page"><PageHeader title="胖墩 Agent" subtitle="从主页、Media Kit、邮件与表格文字提取档案；所有写入必须人工确认" />
    <div className="integration-status-grid">
      {[{ key: 'deepseek' as const, title: 'DeepSeek Agent', detail: status?.model || 'deepseek-v4-flash', configured: Boolean(status?.configured), lastTest: status?.last_test }, { key: 'youtube' as const, title: 'YouTube 数据', detail: status?.youtube?.provider || 'YouTube Data API v3', configured: Boolean(status?.youtube?.configured), lastTest: status?.youtube?.last_test }].map((item) => <article key={item.key} className={`integration-status-card ${item.lastTest?.status || (item.configured ? 'pending' : 'disconnected')}`}><div className="integration-status-icon">{item.lastTest?.status === 'connected' ? <CheckCircle2 size={20} /> : <ShieldCheck size={20} />}</div><div className="integration-status-copy"><header><strong>{item.title}</strong><Tag color={item.lastTest?.status === 'connected' ? 'app-teal' : undefined}>{connectionLabel(item.configured, item.lastTest)}</Tag></header><span>{item.detail}</span><small>最近测试：{item.lastTest?.tested_at ? formatDateTime(item.lastTest.tested_at) : '尚未测试'}{item.lastTest?.message ? ` · ${item.lastTest.message}` : ''}</small></div>{canManage && <Button icon={<RefreshCw size={15} />} disabled={!item.configured || Boolean(testingProvider)} onClick={() => void testConnection(item.key)}>{testingProvider === item.key ? '测试中…' : '测试连接'}</Button>}</article>)}
    </div>
    {(!status?.configured || !status?.youtube?.configured) && <div className="agent-setup"><ShieldCheck size={21} /><div><strong>在本机配置缺少的服务</strong><span>复制 <code>backend/agent.env.example</code> 为 <code>backend/data/agent.env</code>，填写 {!status?.configured && <code>DEEPSEEK_API_KEY</code>} {!status?.configured && !status?.youtube?.configured && '和 '} {!status?.youtube?.configured && <code>YOUTUBE_API_KEY</code>}，然后重启 CRM 生效。网页不会读取、显示或修改密钥。</span></div></div>}
    <div className="agent-layout"><section className="agent-composer"><header><div><Sparkles size={18} /><strong>提取媒体档案</strong></div><span>不会自动写入</span></header><div className="agent-source-tabs"><button className={inputType === 'url' ? 'active' : ''} onClick={() => setInputType('url')}><Link2 size={15} />网页 URL</button><button className={inputType === 'text' ? 'active' : ''} onClick={() => setInputType('text')}><ClipboardList size={15} />粘贴文字</button></div><label>来源名称（可选）<Input value={sourceLabel} onChange={(event) => setSourceLabel(event.target.value)} placeholder="例如：2026 Media Kit 或商务邮件" /></label>{inputType === 'url' ? <label>媒体主页或公开页面<Input value={content} onChange={(event) => setContent(event.target.value)} placeholder="https://..." /></label> : <label>Media Kit、邮件或表格文字<textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="粘贴需要提取的原文；请先移除与 CRM 无关的敏感信息。" /></label>}<footer><span>网页只读取公开文字；不支持登录页面和内网地址</span><Button type="primary" icon={<Sparkles size={15} />} disabled={!canEdit || !status?.configured || content.trim().length < 10 || working} onClick={() => void extract()}>{working ? '正在分析…' : '生成审核预览'}</Button></footer></section><aside className="agent-guardrails"><img src="/assets/pangdun/pangdun_think.png" alt="" /><strong>Agent 能做什么</strong><ul><li>提取名称、国家、渠道与主页</li><li>识别粉丝量、流量和联系人</li><li>显示每个字段的证据与置信度</li><li>匹配 CRM 中已有媒体</li></ul><strong>Agent 不能做什么</strong><ul><li>不能静默修改或删除数据</li><li>不能绕过重复与字典校验</li><li>不能自动发送邮件</li></ul></aside></div>
    <div className="resource-section-heading"><div><h3>最近任务</h3><p>建议、采用、拒绝与失败记录都会保留。</p></div><span>{runs.length} 条</span></div><DataTable data={runs} columns={[{ title: '来源', render: (_: any, row: AgentRun) => <div className="primary-cell"><strong>{row.source_label || '未命名来源'}</strong><span>{row.input_type === 'url' ? '公开网页' : '粘贴文本'} · {formatDateTime(row.created_at)}</span></div>, width: 310 }, { title: '模型', dataIndex: 'model', width: 170 }, { title: '状态', render: (_: any, row: AgentRun) => <Tag color={row.status === 'applied' ? 'app-teal' : undefined}>{({ proposed: '待确认', applied: '已采用', rejected: '已拒绝', failed: '失败', processing: '分析中' } as any)[row.status] || row.status}</Tag>, width: 110 }, { title: '摘要', render: (_: any, row: AgentRun) => row.proposal?.summary || row.error_message || '—', width: 310 }, { title: '管理', render: (_: any, row: AgentRun) => <button className="table-action" onClick={() => openRun(row)}>{row.status === 'proposed' ? '审核建议' : '查看'}</button>, width: 100 }]} />
    {active && <Dialog title={`Agent 审核 · ${active.source_label || `任务 ${active.id}`}`} onClose={() => setActive(null)} footerStart={active.status === 'proposed' ? <Button onClick={() => void reject()}>拒绝建议</Button> : undefined} onOk={active.status === 'proposed' ? () => void apply() : undefined} okLabel={working ? '写入中…' : `确认写入 ${selected.size} 项`}><div className="agent-review"><header><div><Bot size={22} /><div><strong>{active.proposal?.summary || 'Agent 任务记录'}</strong><span>{active.model} · {active.usage?.total_tokens ? `${active.usage.total_tokens} tokens` : '用量未返回'}</span></div></div>{active.proposal?.warnings?.length > 0 && <Tag>{active.proposal.warnings.length} 条提醒</Tag>}</header>{active.proposal?.warnings?.length > 0 && <div className="agent-warnings">{active.proposal.warnings.map((warning: string, index: number) => <span key={index}>{warning}</span>)}</div>}{active.status === 'proposed' && <div className="agent-target"><label><input type="radio" checked={!createMedia} onChange={() => setCreateMedia(false)} />写入现有媒体</label><EntityLookup value={targetMediaId} onChange={setTargetMediaId} options={mediaLookupOptions(media)} placeholder="搜索名称、国家、渠道或主页" /><label><input type="radio" checked={createMedia} onChange={() => { setCreateMedia(true); setTargetMediaId(null); }} />创建新媒体</label></div>}<div className="agent-field-list">{proposalFields(active).map((row) => <label key={row.path} className={row.confidence < .8 ? 'low-confidence' : ''}><input type="checkbox" disabled={active.status !== 'proposed'} checked={selected.has(row.path)} onChange={() => setSelected((current) => { const next = new Set(current); next.has(row.path) ? next.delete(row.path) : next.add(row.path); return next; })} /><div><header><strong>{row.label}</strong><span>{Math.round(row.confidence * 100)}%</span></header><p>{formatAgentValue(row.value)}</p><small>{row.evidence || '模型未提供原文证据，需人工核对'}</small></div></label>)}</div></div></Dialog>}
  </section>;
}

function ProductManager({ canEdit, canManage }: { canEdit: boolean; canManage: boolean }) {
  const [items, setItems] = useState<any[]>([]); const [allProducts, setAllProducts] = useState<any[]>([]); const [q, setQ] = useState(''); const [lineFilter, setLineFilter] = useState(''); const [qualityFilter, setQualityFilter] = useState(''); const [projects, setProjects] = useState<Project[]>([]); const [editing, setEditing] = useState<any>(null); const [merging, setMerging] = useState<any>(null); const [targetProductId, setTargetProductId] = useState<number | null>(null);
  const load = () => api<{ items: any[] }>(`/api/products?q=${encodeURIComponent(q)}&page_size=300`).then((x) => setItems(x.items)); useEffect(() => { void load(); api<{ items: any[] }>('/api/products?page_size=500').then((x) => setAllProducts(x.items)); api<{ items: Project[] }>('/api/projects?page_size=300').then((x) => setProjects(x.items)); }, []);
  const refreshProducts = async () => { await load(); const result = await api<{ items: any[] }>('/api/products?page_size=500'); setAllProducts(result.items); };
  const save = async () => { try { await api(editing.id ? `/api/products/${editing.id}` : '/api/products', { method: editing.id ? 'PUT' : 'POST', body: JSON.stringify(editing) }); setEditing(null); await refreshProducts(); Notification.success({ message: '产品已保存' }); } catch (error) { Notification.error({ message: '保存失败', description: String(error) }); } };
  const remove = async (product: any) => { if (!await confirmAction(`确定删除产品“${product.model}”吗？\n\n若它仍关联历史寄样或执行单，系统会阻止删除，请先使用“合并”。`)) return; try { await api(`/api/products/${product.id}`, { method: 'DELETE' }); await refreshProducts(); Notification.success({ message: '产品已删除' }); } catch (error) { Notification.error({ message: '删除失败', description: String(error) }); } };
  const merge = async () => { if (!merging || !targetProductId) return Notification.error({ message: '请选择合并目标产品' }); const target = allProducts.find((item) => item.id === targetProductId); if (!target || !await confirmAction(`将“${merging.model}”合并到“${target.model}”？\n\n源产品的历史寄样、执行单和项目关联会转移到目标产品，源产品随后删除。此操作不可撤销。`)) return; try { const result = await api<any>(`/api/products/${merging.id}/merge`, { method: 'POST', body: JSON.stringify({ target_product_id: targetProductId }) }); setMerging(null); setTargetProductId(null); await refreshProducts(); Notification.success({ message: `已合并：转移 ${result.shipment_count} 条寄样、${result.campaign_count} 条执行单` }); } catch (error) { Notification.error({ message: '合并失败', description: String(error) }); } };
  const productLines = Array.from(new Set(items.map((item) => item.product_line).filter(Boolean))).sort(); const visibleItems = items.filter((item) => (!lineFilter || item.product_line === lineFilter) && (!qualityFilter || (qualityFilter === 'complete' ? Boolean(item.product_line && item.platform) : !item.product_line || !item.platform)));
  return <section className="resource-page"><PageHeader title="产品库" subtitle="统一维护产品型号与别名，快速了解项目使用和寄样历史" action={<div className="page-actions">{canEdit && <Button type="primary" icon={<Plus size={16} />} onClick={() => setEditing({ model: '', full_name: '', product_line: '', platform: '', aliases: '', notes: '', project_ids: [] })}>新建产品</Button>}<Button className="refresh-button" icon={<RefreshCw size={16} />} onClick={() => void refreshProducts()} aria-label="刷新产品" /></div>} /><div className="resource-toolbar resource-toolbar-flat"><div className="resource-filters resource-filters-leading"><label className="resource-search"><Search size={16} /><input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void load(); }} placeholder="搜索完整型号、全名或别名" /></label><Select compact ariaLabel="按产品线筛选" value={lineFilter} onChange={setLineFilter} options={productLines.map((line) => ({ value: line, label: line }))} placeholder="全部产品线" /><Select compact ariaLabel="按资料状态筛选" value={qualityFilter} onChange={setQualityFilter} options={[{ value: 'complete', label: '资料完整' }, { value: 'incomplete', label: '待补资料' }]} placeholder="全部资料状态" /><Button onClick={() => void load()}>查询</Button></div><span className="resource-result-count">共 {visibleItems.length} 个产品</span></div><DataTable data={visibleItems} columns={[{ title: '产品型号', render: (_: any, r: any) => <button className="primary-cell primary-cell-button" onClick={() => canEdit && setEditing({ ...r })}><strong>{r.model}</strong><span>{r.full_name || r.aliases || '暂无全名或别名'}</span></button>, width: 240 }, { title: '产品归类', render: (_: any, r: any) => <div className="primary-cell"><strong>{r.product_line || '待补产品线'}</strong><span>{r.platform || '待补芯片组 / 平台'}</span></div>, width: 150 }, { title: '使用情况', render: (_: any, r: any) => <div className="primary-cell"><strong>{(r.projects || []).length} 个项目</strong><span>{r.shipment_count || 0} 次历史寄样</span></div>, width: 120 }, { title: '关联项目', render: (_: any, r: any) => (r.projects || []).map((x: any) => x.name).join('、') || '未关联', width: 210 }, { title: '资料状态', render: (_: any, r: any) => <Tag color={r.product_line && r.platform ? 'app-teal' : undefined}>{r.product_line && r.platform ? '资料完整' : '待补资料'}</Tag>, width: 100 }, ...(canEdit ? [{ title: '管理', render: (_: any, r: any) => <div className="row-actions"><button className="table-action" onClick={() => setEditing({ ...r })}><Pencil size={15} />编辑</button>{canManage && <Popover align="end" trigger={<button className="icon-action" aria-label={`管理 ${r.model}`}><MoreHorizontal size={18} /></button>}><div className="record-action-menu"><button onClick={() => { setMerging(r); setTargetProductId(null); }}>合并产品<span>转移引用并保留为目标产品别名</span></button><button className="record-action-menu-danger" onClick={() => void remove(r)}>永久删除<span>仅未被引用的产品可删除</span></button></div></Popover>}</div>, width: 100 }] : [])]} />{editing && <Dialog title={editing.id ? '编辑产品' : '新建产品'} onClose={() => setEditing(null)} onOk={() => void save()}><ProductForm value={editing} projects={projects} setValue={setEditing} /></Dialog>}{merging && <Dialog variant="modal" title={`合并产品 · ${merging.model}`} onClose={() => { setMerging(null); setTargetProductId(null); }} onOk={() => void merge()}><div className="form-grid"><label className="wide">合并到<EntityLookup value={targetProductId} onChange={setTargetProductId} options={allProducts.filter((item) => item.id !== merging.id).map((item) => ({ id: item.id, label: item.model, search: `${item.model} ${item.full_name || ''} ${item.aliases || ''} ${item.platform || ''}` }))} placeholder="输入完整型号、别名或芯片组" /></label><p className="wide merge-warning">源产品的寄样、执行单和项目关联会转移到目标产品；源产品会删除，无法在页面内撤销。</p></div></Dialog>}</section>;
}

function ProductForm({ value, projects, setValue }: { value: any; projects: Project[]; setValue: (value: any) => void }) { const set = (key: string, next: any) => setValue({ ...value, [key]: next }); const toggle = (id: number) => set('project_ids', value.project_ids?.includes(id) ? value.project_ids.filter((x: number) => x !== id) : [...(value.project_ids || []), id]); return <div className="form-grid"><label>完整型号<Input value={value.model || ''} onChange={(e) => set('model', e.target.value)} /></label><label>芯片组 / 平台<Input value={value.platform || ''} onChange={(e) => set('platform', e.target.value)} /></label><label>全名<Input value={value.full_name || ''} onChange={(e) => set('full_name', e.target.value)} /></label><label>产品线<Input value={value.product_line || ''} onChange={(e) => set('product_line', e.target.value)} /></label><label className="wide">别名<Input value={value.aliases || ''} onChange={(e) => set('aliases', e.target.value)} /></label><label className="wide">挂靠推广项目<div className="project-checks">{projects.map((x) => <label key={x.id}><input type="checkbox" checked={value.project_ids?.includes(x.id) || false} onChange={() => toggle(x.id)} />{x.name}</label>)}</div></label><label className="wide">备注<textarea value={value.notes || ''} onChange={(e) => set('notes', e.target.value)} /></label></div>; }

function UsersPage() {
  const [items, setItems] = useState<User[]>([]); const [form, setForm] = useState<any>(null); const load = () => api<{ items: User[] }>('/api/users').then((x) => setItems(x.items)); useEffect(() => { void load(); }, []);
  const save = async () => { if (!form?.name || (!form.id && (!form?.email || !form?.password))) return Notification.error({ message: '请填写完整账号信息' }); if (form.password && form.password.length < 8) return Notification.error({ message: '密码至少 8 位' }); try { const payload = form.id ? { name: form.name, role: form.role, is_active: form.is_active, ...(form.password ? { password: form.password } : {}) } : form; await api(form.id ? `/api/users/${form.id}` : '/api/users', { method: form.id ? 'PUT' : 'POST', body: JSON.stringify(payload) }); setForm(null); await load(); Notification.success({ message: form.id ? '成员设置已更新' : '账号已创建' }); } catch (error) { Notification.error({ message: '保存失败', description: String(error) }); } };
  const roleLabel: Record<string, string> = { Admin: '管理员', Editor: '编辑者', Viewer: '查看者' };
  return <section className="resource-page"><PageHeader title="用户管理" subtitle="为小团队分配清晰、克制的访问权限" action={<Button type="primary" icon={<UserPlus size={16} />} onClick={() => setForm({ name: '', email: '', password: '', role: 'Editor', is_active: true })}>添加成员</Button>} /><div className="role-guide"><ShieldCheck size={22} /><div><strong>三种角色，一眼就够</strong><span><b>管理员</b>可管理成员和永久删除；<b>编辑者</b>负责日常录入与推进；<b>查看者</b>只能浏览。</span></div><small>当前 {items.length} 人</small></div><DataTable data={items} columns={[{ title: '成员', render: (_: any, row: User) => <div className="member-cell"><span>{row.name.slice(0, 1).toUpperCase()}</span><div><strong>{row.name}</strong><small>{row.email}</small></div></div>, width: 320 }, { title: '角色', render: (_: any, row: User) => <div className="primary-cell"><strong>{roleLabel[row.role]}</strong><span>{row.role === 'Admin' ? '成员管理与全部数据权限' : row.role === 'Editor' ? '新增、编辑和推进合作' : '仅查看 CRM 数据'}</span></div>, width: 290 }, { title: '账号状态', render: (_: any, row: User) => <Tag color={row.is_active === false ? undefined : 'app-teal'}>{row.is_active === false ? '已停用' : '正常'}</Tag>, width: 120 }, { title: '管理', render: (_: any, row: User) => <button className="table-action" onClick={() => setForm({ ...row, password: '' })}><UserCog size={16} />管理</button>, width: 100 }]} />{form && <Dialog variant="modal" title={form.id ? `管理成员 · ${form.name}` : '添加团队成员'} onClose={() => setForm(null)} onOk={() => void save()}><div className="form-grid"><label>姓名<Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><label>角色<SelectField value={form.role} onChange={(role) => setForm({ ...form, role })} options={[{ key: 'Admin', label: '管理员（全部权限）' }, { key: 'Editor', label: '编辑者（日常协作）' }, { key: 'Viewer', label: '查看者（只读）' }]} /></label><label className="wide">邮箱<Input type="email" value={form.email} disabled={Boolean(form.id)} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="name@example.com" /></label><label>{form.id ? '重置密码（可选）' : '初始密码'}<Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder={form.id ? '留空则保持不变' : '至少 8 位'} /></label>{form.id && <label>账号状态<SelectField value={form.is_active === false ? 'disabled' : 'active'} onChange={(value) => setForm({ ...form, is_active: value === 'active' })} options={[{ key: 'active', label: '正常' }, { key: 'disabled', label: '停用' }]} /></label>}</div></Dialog>}</section>;
}

export function ExecutionImport() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [batches, setBatches] = useState<any[]>([]);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadBatches = () =>
    api<any>("/api/import-batches").then((result) =>
      setBatches(result.items || []),
    );
  useEffect(() => {
    void loadBatches();
  }, []);
  const generatePreview = async () => {
    if (!file) return Notification.error({ message: "请选择需要导入的文件" });
    const body = new FormData();
    body.append("file", file);
    setBusy(true);
    try {
      const result = await api<any>("/api/universal-import/preview", {
        method: "POST",
        body,
      });
      setPreview(result);
      Notification.success({
        message:
          result.parser === "local_standard"
            ? "已按标准模板生成预览"
            : "Agent 已完成映射，请审核后写入",
      });
    } catch (e) {
      Notification.error({ message: "无法生成预览", description: String(e) });
    } finally {
      setBusy(false);
    }
  };
  const downloadTemplate = async () => {
    try {
      const response = await fetch("/api/universal-import/template.csv", {
        credentials: "include",
      });
      if (!response.ok)
        throw new Error((await response.text()) || response.statusText);
      if (!response.headers.get("content-type")?.includes("text/csv"))
        throw new Error("服务器返回的不是 CSV 文件，请重启 CRM 后重试");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = "Pangdun_CRM_标准导入模板.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      Notification.success({ message: "标准 CSV 已下载" });
    } catch (error) {
      Notification.error({
        message: "模板下载失败",
        description: String(error),
      });
    }
  };
  const confirmImport = async () => {
    if (!preview?.draft_id) return;
    setBusy(true);
    try {
      const result = await api<any>(
        `/api/universal-import/${preview.draft_id}/confirm`,
        { method: "POST" },
      );
      Notification.success({
        message: `处理 ${result.success_count} 条：新增 ${result.created_count || 0}、更新 ${result.updated_count || 0}、跳过 ${result.unchanged_count || 0}`,
      });
      setPreview({ ...preview, confirmed: true });
      await loadBatches();
    } catch (e) {
      Notification.error({ message: "导入失败", description: String(e) });
    } finally {
      setBusy(false);
    }
  };
  const undo = async (batch: any) => {
    if (
      !(await confirmAction(
        `撤销导入批次“${batch.filename || batch.id}”？\n\n本批新增的记录会删除，被导入更新的字段会恢复。`,
      ))
    )
      return;
    try {
      const result = await api<any>(`/api/import-batches/${batch.id}/undo`, {
        method: "POST",
      });
      Notification.success({
        message: `已撤销：删除 ${result.removed} 条，恢复 ${result.restored} 处`,
      });
      await loadBatches();
    } catch (error) {
      Notification.error({ message: "撤销失败", description: String(error) });
    }
  };
  const chooseFile = (next: File | null) => {
    setFile(next);
    setPreview(null);
  };
  return (
    <section className="resource-page import-page">
      <PageHeader
        title="统一导入中心"
        subtitle="标准模板直接映射；其他表格与文档由 Agent 整理，审核后才写入 CRM"
        action={
          <Button
            icon={<Download size={16} />}
            onClick={() => void downloadTemplate()}
          >
            下载标准 CSV
          </Button>
        }
      />
      <ol className="import-steps">
        <li className={file ? "done" : "active"}>
          <span>{file ? "✓" : "1"}</span>
          <div>
            <strong>上传来源</strong>
            <small>表格或文字文档</small>
          </div>
        </li>
        <li className={file && !preview ? "active" : preview ? "done" : ""}>
          <span>{preview ? "✓" : "2"}</span>
          <div>
            <strong>审核映射</strong>
            <small>检查新增、更新与冲突</small>
          </div>
        </li>
        <li className={preview?.confirmed ? "done" : preview ? "active" : ""}>
          <span>{preview?.confirmed ? "✓" : "3"}</span>
          <div>
            <strong>确认写入</strong>
            <small>生成可撤销导入批次</small>
          </div>
        </li>
      </ol>
      <div className="import-workspace">
        <div
          className={`import-dropzone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (event.currentTarget === event.target) setDragging(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            chooseFile(event.dataTransfer.files?.[0] || null);
          }}
        >
          <input
            ref={fileInputRef}
            className="visually-hidden"
            type="file"
            accept=".csv,.xlsx,.pdf,.docx,.txt,.md"
            onChange={(event) => chooseFile(event.target.files?.[0] || null)}
          />
          {file ? (
            <>
              <FileSpreadsheet size={34} />
              <strong>{file.name}</strong>
              <span>
                {(file.size / 1024 / 1024).toFixed(2)} MB ·{" "}
                {preview ? "已生成审核草稿" : "等待解析"}
              </span>
              <Button onClick={() => fileInputRef.current?.click()}>
                更换文件
              </Button>
            </>
          ) : (
            <>
              <UploadCloud size={36} />
              <strong>拖入文件，或从电脑选择</strong>
              <span>支持 CSV、XLSX、PDF、DOCX、TXT、Markdown · 最大 15 MB</span>
              <Button onClick={() => fileInputRef.current?.click()}>
                选择文件
              </Button>
            </>
          )}
        </div>
        <aside className="import-guidance">
          <strong>两种处理方式</strong>
          <ul>
            <li>
              <b>标准 CSV：</b>本地固定字段映射，不调用 Agent
            </li>
            <li>
              <b>其他表格：</b>Agent 只识别表头，逐行处理仍在本地完成
            </li>
            <li>
              <b>文字文档：</b>先在本地提取文字，再由 Agent 整理记录
            </li>
            <li>原文件不长期保存；确认后仍可按批次撤销</li>
          </ul>
        </aside>
      </div>
      <div className="import-actions">
        <Button disabled={!file || busy} onClick={() => void generatePreview()}>
          {busy && !preview ? "正在解析…" : "生成审核预览"}
        </Button>
        <Button
          type="primary"
          disabled={
            !preview?.rows ||
            preview.conflict_count > 0 ||
            preview.confirmed ||
            busy
          }
          onClick={() => void confirmImport()}
        >
          {preview?.confirmed
            ? "已完成导入"
            : `确认导入${preview?.total ? ` ${preview.total} 条` : ""}`}
        </Button>
      </div>
      {preview?.rows && (
        <section className="import-preview">
          <div className="import-summary">
            <div>
              <strong>审核预览 · {preview.total} 条记录</strong>
              <span>
                {preview.parser === "local_standard"
                  ? "标准模板 · 本地规则映射"
                  : preview.parser === "agent_mapping"
                    ? "Agent 已识别原表字段 · 请核对映射结果"
                    : "Agent 已从文档整理记录 · 请核对原文与字段"}
              </span>
            </div>
            <div>
              <b>新增 {preview.created_count || 0}</b>
              <b>更新 {preview.updated_count || 0}</b>
              <b>跳过 {preview.unchanged_count || 0}</b>
              <b className={preview.conflict_count ? "warning-text" : ""}>
                冲突 {preview.conflict_count || 0}
              </b>
            </div>
          </div>
          {preview.parser === "agent_mapping" && (
            <div className="import-mapping">
              <strong>Agent 字段映射</strong>
              <span>
                {Object.entries(preview.mapping || {})
                  .map(([source, target]) => `${source} → ${target}`)
                  .join("　·　")}
              </span>
            </div>
          )}
          {preview.agent_warnings?.map((warning: string) => (
            <p className="warning-text" key={warning}>
              {warning}
            </p>
          ))}
          <DataTable
            data={preview.rows}
            columns={[
              { title: "行", dataIndex: "row_number", width: 60 },
              {
                title: "导入动作",
                render: (_: any, row: any) => (
                  <Tag
                    color={
                      row.import_action === "新增" ? "app-teal" : undefined
                    }
                  >
                    {row.import_action || "已处理"}
                  </Tag>
                ),
                width: 100,
              },
              { title: "合作对象", dataIndex: "media_name", width: 180 },
              {
                title: "项目",
                render: (_: any, row: any) =>
                  row.project_code || row.project_name || "—",
                width: 150,
              },
              {
                title: "执行状态",
                render: (_: any, row: any) =>
                  row.execution_status ? (
                    <StatusTag value={row.execution_status} />
                  ) : (
                    "—"
                  ),
                width: 130,
              },
              {
                title: "产品 / 物流",
                render: (_: any, row: any) => (
                  <div className="primary-cell">
                    <strong>{row.product_bundle || "—"}</strong>
                    <span>{row.tracking_number || "暂无物流单号"}</span>
                  </div>
                ),
                width: 210,
              },
              {
                title: "需确认",
                render: (_: any, row: any) => row.warnings?.join("；") || "无",
                width: 260,
              },
            ]}
          />
        </section>
      )}
      <div className="resource-section-heading">
        <div>
          <h3>导入批次</h3>
          <p>每次确认导入都会留下独立记录，可以安全撤销。</p>
        </div>
        <span>{batches.length} 个批次</span>
      </div>
      <DataTable
        data={batches}
        columns={[
          {
            title: "文件",
            render: (_: any, row: any) => (
              <div className="primary-cell">
                <strong>{row.filename || `批次 ${row.id}`}</strong>
                <span>{new Date(row.created_at).toLocaleString()}</span>
              </div>
            ),
            width: 300,
          },
          {
            title: "类型",
            render: (_: any, row: any) =>
              row.import_type === "universal"
                ? "统一导入"
                : row.import_type === "execution"
                  ? "费用执行表"
                  : "媒体表",
            width: 140,
          },
          {
            title: "导入结果",
            render: (_: any, row: any) =>
              `新增 ${row.summary?.created_count || 0} · 更新 ${row.summary?.updated_count || 0} · 跳过 ${row.summary?.unchanged_count || 0}`,
            width: 300,
          },
          {
            title: "状态",
            render: (_: any, row: any) => (
              <Tag color={row.undone_at ? undefined : "app-teal"}>
                {row.undone_at ? "已撤销" : row.status || "已完成"}
              </Tag>
            ),
            width: 120,
          },
          {
            title: "管理",
            render: (_: any, row: any) =>
              row.undone_at ? (
                "—"
              ) : (
                <button className="table-action" onClick={() => void undo(row)}>
                  撤销本批
                </button>
              ),
            width: 120,
          },
        ]}
      />
    </section>
  );
}

const rootElement = document.getElementById('root') as (HTMLElement & { __pangdunRoot?: ReturnType<typeof createRoot> }) | null;
if (rootElement) {
  const appRoot = rootElement.__pangdunRoot ??= createRoot(rootElement);
  appRoot.render(<><App /><Toaster /><ConfirmHost /></>);
}
