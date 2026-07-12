import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ForceGraph2D from 'react-force-graph-2d';
import { Chat, ExternalQuery } from './Chat';

interface APINode {
  id: string;
  data: {
    name: string;
    symbol_type: string;
    file_path: string;
    commit_count?: number;
  };
}

interface APIEdge {
  id: string;
  source: string;
  target: string;
  label: string;
}

function getHotspotColor(count: number, max: number) {
  if (count === 0) return '#3b3f54';
  const ratio = Math.pow(count / max, 0.5); // non-linear for better visibility
  const r = Math.round(59 + (239 - 59) * ratio);
  const g = Math.round(63 + (68 - 63) * ratio);
  const b = Math.round(84 + (68 - 84) * ratio);
  return `rgb(${r}, ${g}, ${b})`;
}

export const RepoDetail: React.FC = () => {
  const { repoName } = useParams<{ repoName: string }>();
  const navigate = useNavigate();
  const [apiNodes, setApiNodes] = useState<APINode[]>([]);
  const [apiEdges, setApiEdges] = useState<APIEdge[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [hoverNode, setHoverNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [showHotspots, setShowHotspots] = useState(false);
  
  const [externalQuery, setExternalQuery] = useState<ExternalQuery | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const graphRef = useRef<any>();

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(entries => {
      if (entries[0]) {
        setDimensions({
          width: entries[0].contentRect.width,
          height: entries[0].contentRect.height
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Fetch
  useEffect(() => {
    if (!repoName) return;
    fetch(`/api/graph/${encodeURIComponent(repoName)}`)
      .then(res => res.json())
      .then(data => {
        setApiNodes(data.nodes || []);
        setApiEdges(data.edges || []);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, [repoName]);

  const maxCommitCount = useMemo(() => {
    return Math.max(1, ...apiNodes.map(n => n.data.commit_count || 0));
  }, [apiNodes]);

  const graphData = useMemo(() => {
    if (apiNodes.length === 0) return { nodes: [], links: [] };

    const nodeMap = new Map<string, APINode>();
    apiNodes.forEach(n => nodeMap.set(n.id, n));

    const finalNodes = new Map<string, any>();
    const finalEdges = new Map<string, any>();

    const files = new Set(apiNodes.map(n => n.data.file_path));

    files.forEach(file => {
      const fileId = `file:${file}`;
      const firstNodeInFile = apiNodes.find(n => n.data.file_path === file);
      const commitCount = firstNodeInFile?.data.commit_count || 0;

      let color = expandedFiles.has(file) ? '#3b3f54' : '#6366f1';
      if (showHotspots) {
        color = getHotspotColor(commitCount, maxCommitCount);
      }

      finalNodes.set(fileId, {
        id: fileId,
        isFile: true,
        path: file,
        name: file.split(/[/\\]/).pop() || file,
        val: showHotspots ? 3 + (commitCount / maxCommitCount) * 5 : 3,
        color,
        commitCount
      });
    });

    apiNodes.forEach(node => {
      const file = node.data.file_path;
      if (expandedFiles.has(file)) {
        let color = '#8b5cf6';
        if (showHotspots) {
          const count = node.data.commit_count || 0;
          color = getHotspotColor(count, maxCommitCount);
        } else {
          if (node.data.symbol_type === 'class') color = '#ec4899';
          else if (node.data.symbol_type === 'function' || node.data.symbol_type === 'method') color = '#0ea5e9';
          else if (node.data.symbol_type === 'import') color = '#64748b';
        }

        finalNodes.set(node.id, {
          id: node.id,
          isFile: false,
          path: file,
          name: node.data.name,
          type: node.data.symbol_type,
          val: 1,
          color,
          commitCount: node.data.commit_count || 0
        });

        const hubEdgeId = `hub:${node.id}->file:${file}`;
        finalEdges.set(hubEdgeId, {
          id: hubEdgeId,
          source: node.id,
          target: `file:${file}`,
          isHub: true
        });
      }
    });

    apiEdges.forEach(edge => {
      const srcNode = nodeMap.get(edge.source);
      const tgtNode = nodeMap.get(edge.target);
      if (!srcNode || !tgtNode) return;

      const srcFile = srcNode.data.file_path;
      const tgtFile = tgtNode.data.file_path;

      const vSrc = expandedFiles.has(srcFile) ? edge.source : `file:${srcFile}`;
      const vTgt = expandedFiles.has(tgtFile) ? edge.target : `file:${tgtFile}`;

      if (vSrc === vTgt) return;

      const edgeKey = `${vSrc}->${vTgt}`;
      if (!finalEdges.has(edgeKey)) {
        finalEdges.set(edgeKey, {
          id: edgeKey,
          source: vSrc,
          target: vTgt,
          weight: 1,
          isHub: false,
        });
      } else {
        finalEdges.get(edgeKey).weight += 1;
      }
    });

    return {
      nodes: Array.from(finalNodes.values()),
      links: Array.from(finalEdges.values())
    };
  }, [apiNodes, apiEdges, expandedFiles, showHotspots, maxCommitCount]);

  const highlightedNodes = useMemo(() => {
    const set = new Set<string>();
    const activeNode = hoverNode || selectedNode?.id;
    if (activeNode) {
      set.add(activeNode);
      graphData.links.forEach((l: any) => {
        const srcId = typeof l.source === 'object' ? l.source.id : l.source;
        const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
        if (srcId === activeNode) set.add(tgtId);
        if (tgtId === activeNode) set.add(srcId);
      });
    }
    return set;
  }, [hoverNode, selectedNode, graphData.links]);

  const highlightedLinks = useMemo(() => {
    const set = new Set<string>();
    const activeNode = hoverNode || selectedNode?.id;
    if (activeNode) {
      graphData.links.forEach((l: any) => {
        const srcId = typeof l.source === 'object' ? l.source.id : l.source;
        const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
        if (srcId === activeNode || tgtId === activeNode) set.add(l.id);
      });
    }
    return set;
  }, [hoverNode, selectedNode, graphData.links]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node);
    if (node.isFile) {
      setExpandedFiles(prev => {
        const next = new Set(prev);
        if (next.has(node.path)) next.delete(node.path);
        else next.add(node.path);
        return next;
      });
    } else {
      graphRef.current?.centerAt(node.x, node.y, 500);
      graphRef.current?.zoom(4, 500);
    }
  }, []);

  const handleNodeHover = useCallback((node: any) => {
    setHoverNode(node ? node.id : null);
  }, []);

  const drawNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const isHighlighted = highlightedNodes.has(node.id);
    const isHovered = node.id === hoverNode || node.id === selectedNode?.id;
    const isDimmed = (hoverNode || selectedNode) && !isHighlighted;
    
    let r = node.isFile ? (expandedFiles.has(node.path) ? 2 : 6) : 3;
    if (showHotspots && node.isFile && !expandedFiles.has(node.path)) {
      r += (node.commitCount / maxCommitCount) * 4;
    }
    
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
    ctx.fillStyle = isDimmed ? '#1c1f2e' : node.color;
    ctx.fill();
    
    if (isHighlighted && !node.isFile) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 2, 0, 2 * Math.PI, false);
      ctx.strokeStyle = isHovered ? '#ffffff' : node.color;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    
    const label = node.name;
    const showText = node.isFile || isHighlighted || globalScale > 2;
    
    if (showText && !isDimmed) {
      const fontSize = node.isFile ? (expandedFiles.has(node.path) ? 10/globalScale : 14/globalScale) : 10/globalScale;
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      
      const textY = node.y + r + (node.isFile ? 8/globalScale : 6/globalScale);
      
      ctx.fillStyle = node.isFile ? '#e2e8f0' : '#94a3b8';
      if (isHovered) ctx.fillStyle = '#ffffff';
      
      ctx.fillText(label, node.x, textY);
    }
  }, [highlightedNodes, hoverNode, selectedNode, expandedFiles, showHotspots, maxCommitCount]);

  const handleZoomIn = () => {
    const currentZoom = graphRef.current?.zoom();
    if (currentZoom) graphRef.current?.zoom(currentZoom * 1.5, 300);
  };
  
  const handleZoomOut = () => {
    const currentZoom = graphRef.current?.zoom();
    if (currentZoom) graphRef.current?.zoom(currentZoom / 1.5, 300);
  };

  const handleZoomFit = () => {
    graphRef.current?.zoomToFit(400, 40);
  };

  const handleExplain = () => {
    if (!selectedNode) return;
    const typeStr = selectedNode.isFile ? "file" : (selectedNode.type || "symbol");
    const prompt = `Explain the ${typeStr} "${selectedNode.name}" located in "${selectedNode.path}". What is its purpose?`;
    setExternalQuery({ text: prompt, timestamp: Date.now() });
  };

  return (
    <div style={{ height: '100vh', width: '100%', display: 'flex' }}>
      
      {/* Left side: Graph */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        <div style={{ padding: '16px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: 16 }}>
          <button className="btn-ghost" onClick={() => navigate('/')}>← Back</button>
          <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>{repoName} Dependency Graph</h2>
        </div>
        
        <div ref={containerRef} style={{ flex: 1, background: 'var(--bg-primary)', overflow: 'hidden' }} onClick={(e) => {
          if (e.target instanceof HTMLCanvasElement && !hoverNode) {
            setSelectedNode(null);
          }
        }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)' }}>
              Loading force graph...
            </div>
          ) : (
            <ForceGraph2D
              ref={graphRef}
              width={dimensions.width}
              height={dimensions.height}
              graphData={graphData}
              
              nodeRelSize={4}
              nodeVal={node => (node as any).val}
              nodeColor={node => (node as any).color}
              
              onNodeClick={handleNodeClick}
              onNodeHover={handleNodeHover}
              
              nodeCanvasObject={drawNode}
              
              linkColor={(link: any) => {
                if (link.isHub) return 'rgba(255, 255, 255, 0.05)';
                const isDimmed = (hoverNode || selectedNode) && !highlightedLinks.has(link.id);
                if (isDimmed) return 'rgba(255, 255, 255, 0.02)';
                if (highlightedLinks.has(link.id)) return 'rgba(99, 102, 241, 0.8)';
                return 'rgba(148, 163, 184, 0.2)';
              }}
              linkWidth={(link: any) => {
                if (link.isHub) return 0.5;
                return highlightedLinks.has(link.id) ? 2 : Math.min(2, link.weight * 0.5);
              }}
              linkDirectionalArrowLength={(link: any) => link.isHub ? 0 : (highlightedLinks.has(link.id) ? 4 : 2)}
              linkDirectionalArrowRelPos={1}
              
              d3AlphaDecay={0.05}
              d3VelocityDecay={0.2}
            />
          )}
        </div>

        {/* Legend Panel */}
        <div className="glass-card fade-in" style={{ position: 'absolute', bottom: 24, left: 24, padding: '16px', display: 'flex', flexDirection: 'column', gap: 12, fontSize: 13, background: 'var(--bg-card)' }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Legend</div>
          {!showHotspots ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: '#6366f1', fontSize: 16 }}>●</span> File (Collapsed)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: '#3b3f54', fontSize: 16 }}>●</span> File (Expanded)</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: '#ec4899', fontSize: 16 }}>●</span> Class</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: '#0ea5e9', fontSize: 16 }}>●</span> Function / Method</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: '#64748b', fontSize: 16 }}>●</span> Import / Other</div>
            </>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: '#ef4444', fontSize: 16 }}>●</span> High Git Churn</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ color: '#3b3f54', fontSize: 16 }}>●</span> Low Git Churn</div>
            </>
          )}
        </div>

        {/* Controls Panel */}
        <div style={{ position: 'absolute', bottom: 24, right: 24, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button 
            className="glass-card" 
            style={{ padding: '8px 12px', color: showHotspots ? 'var(--accent-primary)' : 'white', cursor: 'pointer', background: 'var(--bg-card)', border: showHotspots ? '1px solid var(--accent-primary)' : '1px solid var(--border-color)', fontSize: 14, fontWeight: 600 }} 
            onClick={() => setShowHotspots(!showHotspots)}
          >
            🔥 Git Hotspots
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="glass-card" style={{ width: 40, height: 40, color: 'white', cursor: 'pointer', background: 'var(--bg-card)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }} onClick={handleZoomIn}>+</button>
            <button className="glass-card" style={{ width: 40, height: 40, color: 'white', cursor: 'pointer', background: 'var(--bg-card)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }} onClick={handleZoomOut}>-</button>
            <button className="glass-card" style={{ width: 40, height: 40, color: 'white', cursor: 'pointer', background: 'var(--bg-card)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }} onClick={handleZoomFit}>⌖</button>
          </div>
        </div>

        {/* Selected Node Details Tooltip overlay (in graph area) */}
        {selectedNode && (
          <div className="glass-card fade-in" style={{ position: 'absolute', top: 24, right: 24, padding: '20px', width: '320px', background: 'var(--bg-card)', border: '1px solid var(--accent-primary)', boxShadow: 'var(--shadow-lg)', zIndex: 50 }}>
            <div style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, marginBottom: 4 }}>
              {selectedNode.isFile ? 'File' : selectedNode.type || 'Symbol'}
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', wordBreak: 'break-all', marginBottom: 8 }}>
              {selectedNode.name}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', wordBreak: 'break-all', marginBottom: 8 }}>
              {selectedNode.path}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>
              Commits (90d): {selectedNode.commitCount || 0}
            </div>
            <button className="btn-primary" style={{ width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8 }} onClick={handleExplain}>
              <span>✨</span> Explain with AI
            </button>
          </div>
        )}
      </div>

      {/* Right side: Chat Panel */}
      <div style={{ width: '400px', borderLeft: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)', zIndex: 10 }}>
        <Chat isSidePanel={true} repoOverride={repoName} externalQuery={externalQuery} />
      </div>

    </div>
  );
};