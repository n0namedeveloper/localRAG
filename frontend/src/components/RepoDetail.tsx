import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
} from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';

// Custom node for better styling
const CustomNode = ({ data }: any) => {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: `2px solid ${data.color}`,
      padding: '10px 16px',
      borderRadius: '8px',
      minWidth: 150,
      textAlign: 'center',
      boxShadow: 'var(--shadow-sm)'
    }}>
      <Handle type="target" position={Position.Top} style={{ background: data.color }} />
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>{data.symbol_type}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', wordBreak: 'break-all' }}>{data.label}</div>
      <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>{data.file}</div>
      <Handle type="source" position={Position.Bottom} style={{ background: data.color }} />
    </div>
  );
};

const nodeTypes = { custom: CustomNode };

export const RepoDetail: React.FC = () => {
  const { repoName } = useParams<{ repoName: string }>();
  const navigate = useNavigate();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);

  // Layout function using Dagre
  const getLayoutedElements = (nodes: any[], edges: any[], direction = 'TB') => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ rankdir: direction });

    nodes.forEach((node) => {
      dagreGraph.setNode(node.id, { width: 250, height: 100 });
    });

    edges.forEach((edge) => {
      dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    nodes.forEach((node) => {
      const nodeWithPosition = dagreGraph.node(node.id);
      node.targetPosition = Position.Top;
      node.sourcePosition = Position.Bottom;
      // We are shifting the dagre node position (anchor=center center) to the top left
      // so it matches the React Flow node anchor point (top left).
      node.position = {
        x: nodeWithPosition.x - 250 / 2,
        y: nodeWithPosition.y - 100 / 2,
      };
      return node;
    });

    return { nodes, edges };
  };

  useEffect(() => {
    if (!repoName) return;
    fetch(`/api/graph/${encodeURIComponent(repoName)}`)
      .then(res => res.json())
      .then(data => {
        if (!data.nodes) return;
        
        const initialNodes = data.nodes.map((n: any) => {
          let color = '#6366f1'; // function
          if (n.data.symbol_type === 'class') color = '#8b5cf6';
          if (n.data.symbol_type === 'import') color = '#475569';
          
          return {
            id: n.id,
            type: 'custom',
            data: { 
              label: n.data.name,
              symbol_type: n.data.symbol_type,
              file: n.data.file_path,
              color
            },
            position: { x: 0, y: 0 },
          };
        });

        const initialEdges = data.edges.map((e: any) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
          animated: true,
          style: { stroke: 'var(--border-hover)', strokeWidth: 2 },
          labelStyle: { fill: 'var(--text-secondary)', fontSize: 10 },
          labelBgStyle: { fill: 'var(--bg-primary)' },
          markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--border-hover)' }
        }));

        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(initialNodes, initialEdges);
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, [repoName]);

  return (
    <div style={{ height: '100vh', width: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '16px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: 16 }}>
        <button className="btn-ghost" onClick={() => navigate('/')}>← Back</button>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>{repoName} Dependency Graph</h2>
      </div>
      <div style={{ flex: 1, background: 'var(--bg-primary)' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>Loading graph layout...</div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.1}
          >
            <Controls style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', fill: 'var(--text-primary)' }} />
            <MiniMap style={{ background: 'var(--bg-card)' }} maskColor="rgba(0,0,0,0.5)" nodeColor="#6366f1" />
            <Background color="var(--border-hover)" gap={20} />
          </ReactFlow>
        )}
      </div>
    </div>
  );
};