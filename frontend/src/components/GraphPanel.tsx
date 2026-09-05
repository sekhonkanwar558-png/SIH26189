import cytoscape from 'cytoscape'
import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { CaseGraph } from '../types'

/**
 * The graph, shown when an answer has a route to show — never as a place to go.
 *
 * D25: there is no Connections tab any more. An officer does not open a graph;
 * he asks a question, and if the answer is a path through the case then the path
 * is what he sees, lit in the one colour this product uses for meaning (D28).
 * Everything else on the canvas stays grey, because it is context, not claim.
 */

const INK = '#0d0d0d'
const GREY = '#c9c9cf'
const AMBER = '#b8791f'

export interface GraphPanelProps {
  graph: CaseGraph
  /** Ordered node ids the answer rests on. Lit hop by hop. */
  path: string[]
  onClose: () => void
  onOpenNode?: (nodeId: string) => void
}

export function GraphPanel({ graph, path, onClose, onOpenNode }: GraphPanelProps) {
  const host = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  useEffect(() => {
    if (!host.current) return

    const onPath = new Set(path)
    // Only the edges that actually join two consecutive hops are lit. Nothing is
    // ever drawn between two nodes with no edge between them — that would be the
    // graph illustrating the answer instead of causing it.
    const hops = new Set<string>()
    for (let i = 0; i < path.length - 1; i += 1) {
      hops.add(`${path[i]}|${path[i + 1]}`)
      hops.add(`${path[i + 1]}|${path[i]}`)
    }

    const nodes = graph.nodes.map((node) => ({
      data: { id: node.id, label: node.label, lit: onPath.has(node.id) ? 1 : 0 },
    }))
    const known = new Set(graph.nodes.map((n) => n.id))
    const edges = graph.edges
      .filter((edge) => known.has(edge.src) && known.has(edge.dst))
      .map((edge) => ({
        data: {
          id: edge.id,
          source: edge.src,
          target: edge.dst,
          lit: hops.has(`${edge.src}|${edge.dst}`) ? 1 : 0,
        },
      }))

    const cy = cytoscape({
      container: host.current,
      elements: { nodes, edges },
      style: [
        {
          selector: 'node',
          style: {
            'background-color': GREY,
            width: 9,
            height: 9,
            label: '',
          },
        },
        {
          selector: 'node[lit = 1]',
          style: {
            'background-color': AMBER,
            width: 20,
            height: 20,
            label: 'data(label)',
            'font-size': 11,
            'font-family': 'Inter Variable, Inter, system-ui, sans-serif',
            color: INK,
            'text-margin-y': -8,
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'straight',
            width: 1,
            'line-color': '#ececef',
            opacity: 0.7,
          },
        },
        {
          selector: 'edge[lit = 1]',
          style: { 'line-color': AMBER, width: 2.5, opacity: 1 },
        },
      ],
      layout: {
        name: 'cose',
        animate: false,
        nodeRepulsion: 9000,
        idealEdgeLength: 60,
        padding: 40,
      } as cytoscape.LayoutOptions,
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    })

    cyRef.current = cy
    if (onOpenNode) {
      cy.on('tap', 'node', (event) => onOpenNode(event.target.id() as string))
    }

    // Cytoscape sets `position: relative` on its container at runtime, which
    // beats a Tailwind `absolute` and collapses the canvas to zero height. The
    // container is sized inline, and a ResizeObserver keeps it right when the
    // panel opens, closes or the window changes.
    const fit = () => {
      cy.resize()
      if (onPath.size) cy.fit(cy.nodes('[lit = 1]'), 80)
      else cy.fit(undefined, 40)
    }
    fit()
    const observer = new ResizeObserver(fit)
    observer.observe(host.current)

    return () => {
      observer.disconnect()
      cy.destroy()
      cyRef.current = null
    }
  }, [graph, path, onOpenNode])

  return (
    <aside className="flex h-full min-h-0 w-full flex-col border-l border-line bg-canvas">
      <header className="flex shrink-0 items-center gap-3 px-4 py-3">
        <p className="text-[13px] text-muted">
          {path.length > 1
            ? `The route this answer rests on — ${path.length} steps`
            : path.length === 1
              ? 'What this answer is about'
              : `${graph.nodes.length} entities in this case`}
        </p>
        <button
          type="button"
          onClick={onClose}
          aria-label="Hide the graph"
          className="ml-auto rounded-lg p-1.5 text-subtle transition hover:bg-raised hover:text-ink"
        >
          <X size={16} />
        </button>
      </header>
      <div
        ref={host}
        className="min-h-0 flex-1"
        style={{ position: 'relative', width: '100%' }}
      />
    </aside>
  )
}
