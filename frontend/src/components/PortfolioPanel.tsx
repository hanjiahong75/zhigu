import { useState, useEffect } from 'react';
import { Button, Table, InputNumber, Input, Select, Card, Statistic, Space, Popconfirm, App, Spin } from 'antd';
import { DeleteOutlined, SaveOutlined, PlusOutlined } from '@ant-design/icons';
import { getPortfolio, getPortfolioRisk, updatePortfolioItems, deletePortfolio } from '../api/client';
import type { Portfolio, PortfolioItem } from '../types';

interface EditableItem {
  key: string;
  stock_code: string;
  stock_name: string;
  asset_type: string;
  quantity: number;
  cost_price: number;
  current_price: number;
}

interface RiskData {
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  message: string | null;
}

export default function PortfolioPanel() {
  const { message } = App.useApp();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [editItems, setEditItems] = useState<EditableItem[]>([]);
  const [hasChanges, setHasChanges] = useState(false);
  const [risk, setRisk] = useState<RiskData | null>(null);

  useEffect(() => { loadPortfolio(); }, []);
  useEffect(() => { if (portfolio?.items?.length) loadRisk(); }, [portfolio?.items?.length]);

  const loadPortfolio = async () => {
    setLoading(true);
    try {
      const data = await getPortfolio();
      setPortfolio(data);
      if (data.items && data.items.length > 0) {
        setEditItems(data.items.map((item: PortfolioItem, idx: number) => ({
          key: String(item.id || idx),
          stock_code: item.stock_code,
          stock_name: item.stock_name,
          asset_type: item.asset_type,
          quantity: item.quantity,
          cost_price: item.cost_price,
          current_price: item.current_price,
        })));
      }
    } catch { message.error('加载持仓失败'); }
    setLoading(false);
  };

  const loadRisk = async () => {
    try { const data = await getPortfolioRisk(); setRisk(data); } catch { /* silent */ }
  };

  const handleSave = async () => {
    const validItems = editItems.filter(item => item.stock_name);
    if (validItems.length === 0) { message.warning('请添加持仓数据'); return; }
    try {
      await updatePortfolioItems(validItems);
      message.success('持仓保存成功');
      setHasChanges(false);
      loadPortfolio();
    } catch { message.error('保存失败'); }
  };

  const handleClear = async () => {
    try {
      await deletePortfolio();
      setPortfolio(null);
      setEditItems([]);
      setRisk(null);
      setHasChanges(false);
      message.success('持仓已清空');
    } catch { message.error('清空失败'); }
  };

  const handleItemChange = (key: string, field: string, value: any) => {
    setEditItems(prev => prev.map(item => item.key === key ? { ...item, [field]: value } : item));
    setHasChanges(true);
  };

  const handleAddRow = () => {
    setEditItems(prev => [...prev, {
      key: 'manual_' + Date.now(), stock_code: '', stock_name: '',
      asset_type: 'stock', quantity: 0, cost_price: 0, current_price: 0,
    }]);
    setHasChanges(true);
  };

  const handleRemoveRow = (key: string) => {
    setEditItems(prev => prev.filter(item => item.key !== key));
    setHasChanges(true);
  };

  const columns = [
    { title: '代码', dataIndex: 'stock_code', width: 90, render: (_: any, r: EditableItem) => (
      <Input size="small" value={r.stock_code} onChange={e => handleItemChange(r.key, 'stock_code', e.target.value)} placeholder="选填" style={{ width: 80 }} />
    )},
    { title: '名称', dataIndex: 'stock_name', width: 100, render: (_: any, r: EditableItem) => (
      <Input size="small" value={r.stock_name} onChange={e => handleItemChange(r.key, 'stock_name', e.target.value)} placeholder="必填" style={{ width: 90 }} />
    )},
    { title: '类型', dataIndex: 'asset_type', width: 70, render: (_: any, r: EditableItem) => (
      <Select size="small" value={r.asset_type} onChange={v => handleItemChange(r.key, 'asset_type', v)} style={{ width: 65 }}
        options={[{ label: '股票', value: 'stock' }, { label: 'ETF', value: 'etf' }, { label: '基金', value: 'fund' }]} />
    )},
    { title: '数量', dataIndex: 'quantity', width: 70, render: (_: any, r: EditableItem) => (
      <InputNumber size="small" value={r.quantity} onChange={v => handleItemChange(r.key, 'quantity', v || 0)} style={{ width: 65 }} min={0} />
    )},
    { title: '成本价', dataIndex: 'cost_price', width: 70, render: (_: any, r: EditableItem) => (
      <InputNumber size="small" value={r.cost_price} onChange={v => handleItemChange(r.key, 'cost_price', v || 0)} style={{ width: 65 }} min={0} precision={3} />
    )},
    { title: '', width: 30, render: (_: any, r: EditableItem) => (
      <Button type="text" size="small" icon={<DeleteOutlined />} onClick={() => handleRemoveRow(r.key)} danger />
    )},
  ];

  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>;

  return (
    <div style={{ padding: 12 }}>
      {portfolio && portfolio.items && portfolio.items.length > 0 && (
        <Card size="small" style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <Statistic title="总市值" value={portfolio.total_value} precision={0} suffix="元" valueStyle={{ fontSize: 14 }} />
            <Statistic title="总盈亏" value={portfolio.total_profit} precision={0} suffix="元"
              valueStyle={{ fontSize: 14, color: portfolio.total_profit >= 0 ? '#cf1322' : '#3f8600' }} />
            <Statistic title="收益率" value={portfolio.total_profit_pct} precision={2} suffix="%"
              valueStyle={{ fontSize: 14, color: portfolio.total_profit >= 0 ? '#cf1322' : '#3f8600' }} />
          </div>
        </Card>
      )}

      {risk && (risk.sharpe_ratio !== null || risk.max_drawdown !== null) && (
        <Card size="small" style={{ marginBottom: 12, background: '#fafafa' }}>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>风险分析</div>
          <div style={{ display: 'flex', gap: 24 }}>
            {risk.sharpe_ratio !== null && (
              <Statistic title="夏普比率" value={risk.sharpe_ratio} precision={2}
                valueStyle={{ fontSize: 14, color: risk.sharpe_ratio >= 1 ? '#3f8600' : risk.sharpe_ratio >= 0 ? '#333' : '#cf1322' }} />
            )}
            {risk.max_drawdown !== null && (
              <Statistic title="最大回撤" value={risk.max_drawdown} precision={2} suffix="%"
                valueStyle={{ fontSize: 14, color: risk.max_drawdown <= 20 ? '#3f8600' : risk.max_drawdown <= 40 ? '#faad14' : '#cf1322' }} />
            )}
          </div>
        </Card>
      )}
      {risk?.message && <div style={{ fontSize: 11, color: '#bbb', marginBottom: 8 }}>{risk.message}</div>}

      {editItems.length > 0 && (
        <>
          <Table dataSource={editItems} columns={columns} size="small" pagination={false} scroll={{ x: 420 }} style={{ marginBottom: 8 }} />
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Button size="small" icon={<PlusOutlined />} onClick={handleAddRow}>添加</Button>
            <Space>
              {portfolio && portfolio.items && portfolio.items.length > 0 && (
                <Popconfirm title="确定清空持仓？" onConfirm={handleClear} okText="确定" cancelText="取消">
                  <Button size="small" danger icon={<DeleteOutlined />}>清空</Button>
                </Popconfirm>
              )}
              <Button type="primary" size="small" icon={<SaveOutlined />} onClick={handleSave} disabled={!hasChanges}>保存</Button>
            </Space>
          </Space>
        </>
      )}

      {editItems.length === 0 && (
        <div style={{ textAlign: 'center', padding: 20, color: '#999' }}>
          <p>暂无持仓数据</p>
          <Button size="small" icon={<PlusOutlined />} onClick={handleAddRow}>手动添加</Button>
        </div>
      )}
    </div>
  );
}