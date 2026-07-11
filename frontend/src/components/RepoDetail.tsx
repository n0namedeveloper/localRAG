import React, { useEffect, useState } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  Node,
  Edge,
  useNodesState,
  useEdgesState
} from 'react-flow-renderer';
import 'react-flow-renderer/dist/style.css';

interface GraphData {
  repo_name: string;
  nodes: Array<{
    id: string;
    data: {
      name: string;
      symbol_type: string;
      file_path: string;
    };
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    label: string;
  }>;
}

export const RepoDetail: React.FC<{ repoName?: string }> = ({ repoName }) => {
  if (!repoName) {
    throw new Error('Repository name is required');
  }
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [nodes, setNodes] = useNodesState([]);
  const [edges, setEdges] = useEdgesState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/graph/${repoName}`)
      .then(res => res.json())
      .then((data: GraphData) => {
        setGraphData(data);
        const flowNodes: Node[] = data.nodes.map(n => ({
          id: n.id,
          data: { label: `${n.data.name} (${n.data.symbol_type})` },
          position: { x: Math.random() * 500, y: Math.random() * 500 },
          style: {
            background: n.data.symbol_type === 'function' ? '#e3f2fd' : 
                       n.data.symbol_type === 'class' ? '#f3e5f5' : '#fff',
            border: '1px solid #999',
            borderRadius: 3,
            padding: 10,
          }
        }));
        const flowEdges: Edge[] = data.edges.map(e => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
          animated: true,
        }));
        setNodes(flowNodes);
        setEdges(flowEdges);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch graph:', err);
        setLoading(false);
      });
  }, [repoName]);

  if (loading) return <div className="flex justify-center p-8">Loading graph...</div>;
  if (!graphData) return <div className="text-red-500 p-8">Failed to load graph data</div>;

  return (
    <div className="h-[600px] w-full border rounded-lg overflow-hidden">
      <div className="bg-gray-100 px-4 py-2 border-b">
        <h2 className="font-semibold">{graphData.repo_name} - Dependency Graph</h2>
        <div className="text-sm text-gray-600">
          Nodes: {graphData.nodes.length} | Edges: {graphData.edges.length}
        </div>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        attributionPosition="bottom-right"
      >
        <Controls />
        <MiniMap />
        <Background color="#aaa" gap={16} />
      </ReactFlow>
    </div>
  );
};