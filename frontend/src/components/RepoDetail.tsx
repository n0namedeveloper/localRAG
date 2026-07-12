import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ForceGraph2D from 'react-force-graph-2d';

interface APINode {
  id: string;
  data: {
    name: string;
    symbol_type: string;
    file_path: string;
  };
}

interface APIEdge {
  id: string;
  source: string;
  target: string;
  label: string;
}

export const RepoDetail: React.FC = () => {
  const { repoName } = useParams<{ repoName: string }>();
  const navigate = useNavigate();
  const [apiNodes, setApiNodes] = useState<APINode[]>([]);
  const [apiEdges, setApiEdges] = useState<APIEdge[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [hoverNode, setHoverNode] = useState<string | null>(null);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const graphRef = useRef<any>();

  // Resize observer for responsive canvas
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

  // Fetch API data
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

  // Derived graph data computation
  const graphData = useMemo(() => {
    if (apiNodes.length === 0) return { nodes: [], links: [] };

    const nodeMap = new Map<string, APINode>();
    apiNodes.forEach(n => nodeMap.set(n.id, n));

    const finalNodes = new Map<string, any>();
    const finalEdges = new Map<string, any>();

    const files = new Set(apiNodes.map(n => n.data.file_path));

    // 1. Create File nodes
    files.forEach(file => {
      const fileId = `file:${file}`;
      finalNodes.set(fileId, {
        id: fileId,
        isFile: true,
        path: file,
        name: file.split(/[/\\]/).pop() || file,
        val: 3, // slightly larger
        color: expandedFiles.has(file) ? '#3b3f54' : '#6366f1',
      });
    });

    // 2. Create Symbol nodes if file is expanded
    apiNodes.forEach(node => {
      const file = node.data.file_path;
      if (expandedFiles.has(file)) {
        let color = '#8b5cf6'; // default
        if (node.data.symbol_type === 'class') color = '#ec4899';
        else if (node.data.symbol_type === 'function' || node.data.symbol_type === 'method') color = '#0ea5e9';
        else if (node.data.symbol_type === 'import') color = '#64748b';

        finalNodes.set(node.id, {
          id: node.id,
          isFile: false,
          path: file,
          name: node.data.name,
          type: node.data.symbol_type,
          val: 1,
          color,
        });

        // Link symbol to its File hub (invisible or faint link) to keep them clustered
        const hubEdgeId = `hub:${node.id}->file:${file}`;
        finalEdges.set(hubEdgeId, {
          id: hubEdgeId,
          source: node.id,
          target: `file:${file}`,
          isHub: true
        });
      }
    });

    // 3. Process API edges and aggregate them based on expansion state
    apiEdges.forEach(edge => {
      const srcNode = nodeMap.get(edge.source);
      const tgtNode = nodeMap.get(edge.target);
      if (!srcNode || !tgtNode) return;

      const srcFile = srcNode.data.file_path;
      const tgtFile = tgtNode.data.file_path;

      // Determine visual source/target based on expansion
      const vSrc = expandedFiles.has(srcFile) ? edge.source : `file:${srcFile}`;
      const vTgt = expandedFiles.has(tgtFile) ? edge.target : `file:${tgtFile}`;

      if (vSrc === vTgt) return; // Skip self-edges if they resolve to the same node (e.g. within unexpanded file)

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
        finalEdges.get(edgeKey).weight += 1; // aggregate weights
      }
    });

    return {
      nodes: Array.from(finalNodes.values()),
      links: Array.from(finalEdges.values())
    };
  }, [apiNodes, apiEdges, expandedFiles]);

  // Compute highlighting (hovered node and its 1-hop neighbors)
  const highlightedNodes = useMemo(() => {
    const set = new Set<string>();
    if (hoverNode) {
      set.add(hoverNode);
      graphData.links.forEach((l: any) => {
        // react-force-graph replaces source/target string IDs with object references during render
        const srcId = typeof l.source === 'object' ? l.source.id : l.source;
        const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
        
        if (srcId === hoverNode) set.add(tgtId);
        if (tgtId === hoverNode) set.add(srcId);
      });
    }
    return set;
  }, [hoverNode, graphData.links]);

  const highlightedLinks = useMemo(() => {
    const set = new Set<string>();
    if (hoverNode) {
      graphData.links.forEach((l: any) => {
        const srcId = typeof l.source === 'object' ? l.source.id : l.source;
        const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
        if (srcId === hoverNode || tgtId === hoverNode) set.add(l.id);
      });
    }
    return set;
  }, [hoverNode, graphData.links]);

  // Interactions
  const handleNodeClick = useCallback((node: any) => {
    if (node.isFile) {
      setExpandedFiles(prev => {
        const next = new Set(prev);
        if (next.has(node.path)) next.delete(node.path);
        else next.add(node.path);
        return next;
      });
    } else {
      // Could fly to node or center it
      graphRef.current?.centerAt(node.x, node.y, 500);
      graphRef.current?.zoom(4, 500);
    }
  }, []);

  const handleNodeHover = useCallback((node: any) => {
    setHoverNode(node ? node.id : null);
  }, []);

  // Custom node drawing on Canvas
  const drawNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const isHighlighted = highlightedNodes.has(node.id);
    const isHovered = node.id === hoverNode;
    const isDimmed = hoverNode && !isHighlighted;
    
    const r = node.isFile ? (expandedFiles.has(node.path) ? 2 : 6) : 3;
    
    // Draw circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
    ctx.fillStyle = isDimmed ? '#1c1f2e' : node.color;
    ctx.fill();
    
    // Hover ring
    if (isHighlighted && !node.isFile) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 2, 0, 2 * Math.PI, false);
      ctx.strokeStyle = isHovered ? '#ffffff' : node.color;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    
    // Text rendering logic (only render if zoomed in enough or if highlighted/file)
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
  }, [highlightedNodes, hoverNode, expandedFiles]);

  return (
    <div style={{ height: '100vh', width: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '16px 24px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: 16 }}>
        <button className="btn-ghost" onClick={() => navigate('/')}>← Back</button>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>{repoName} Dependency Graph</h2>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
          <div><span style={{ color: '#6366f1' }}>●</span> File</div>
          <div><span style={{ color: '#8b5cf6' }}>●</span> Class</div>
          <div><span style={{ color: '#0ea5e9' }}>●</span> Function/Method</div>
        </div>
      </div>
      
      <div ref={containerRef} style={{ flex: 1, background: 'var(--bg-primary)', overflow: 'hidden' }}>
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
            
            // Interaction
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            
            // Custom drawing
            nodeCanvasObject={drawNode}
            
            // Link styling
            linkColor={(link: any) => {
              if (link.isHub) return 'rgba(255, 255, 255, 0.05)'; // almost invisible hubs
              const isDimmed = hoverNode && !highlightedLinks.has(link.id);
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
            
            // Engine settings
            d3AlphaDecay={0.05}
            d3VelocityDecay={0.2}
          />
        )}
      </div>
    </div>
  );
};