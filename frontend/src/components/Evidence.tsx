import { useQuery } from '@tanstack/react-query'
import { ChevronRight, FileText } from 'lucide-react'
import { useState } from 'react'
import { getNode, getSource } from '../lib/api'
import type { AgentAnswer, GraphNode, SourceExcerpt } from '../types'

/**
 * What an answer rests on — the trail from a sentence back to the line in the
 * document it came from.
 *
 * This is the "how do you know?" a judge asks in the first minute, and until it
 * existed the answer was invisible: the backend verified every citation against
 * the real graph and then showed the officer none of it. **The claim that the
 * graph causes the answer (D3) has to be checkable by the person reading it**,
 * or it is a claim about our code rather than a property of the product.
 *
 * It stays folded. An officer reading a paragraph should not have to look past
 * a citation apparatus to find the next sentence — he opens this when he
 * doubts something, which is exactly when it should cost him one click.
 */

const TYPE_WORD: Record<string, string> = {
  person: 'person',
  phone: 'number',
  organization: 'organisation',
  location: 'place',
  vehicle: 'vehicle',
  account: 'account',
  device: 'device',
  event: 'prior case',
  document: 'document',
}

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`
}

/** One cited entity: what it is, and the line of the document it came out of. */
function Entity({ caseId, nodeId }: { caseId: string; nodeId: string }) {
  const [open, setOpen] = useState(false)
  const [excerpt, setExcerpt] = useState<SourceExcerpt | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Fetched as soon as the trail is shown, not when the row is expanded. The
  // row has to be able to say "Manjit Singh" — an officer is never shown an id
  // (D26), and `person:manjit_singh` is an id with the punctuation taken out.
  const profile = useQuery({
    queryKey: ['node', caseId, nodeId],
    queryFn: () => getNode(caseId, nodeId),
    staleTime: 60_000,
  })

  async function show(node: GraphNode) {
    const ref = node.sources[0]
    if (!ref) return
    try {
      setExcerpt(await getSource(caseId, ref.doc_id, ref.start, ref.end))
    } catch {
      setError('That source could not be opened.')
    }
  }

  const node = profile.data?.node
  const label = node?.label ?? '…'
  const kind = node ? TYPE_WORD[node.type] ?? node.type : null

  return (
    <div className="border-b border-line last:border-0">
      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        className="flex w-full items-center gap-2 py-2 text-left text-[13px] text-ink transition hover:text-evidence"
      >
        <ChevronRight
          size={13}
          className={`shrink-0 text-subtle transition-transform ${open ? 'rotate-90' : ''}`}
        />
        <span className="truncate">{label}</span>
        {kind && <span className="shrink-0 text-[12px] text-subtle">{kind}</span>}
      </button>

      {open && (
        <div className="pb-3 pl-[21px]">
          {error && <p className="text-[12px] text-danger">{error}</p>}
          {profile.isError && <p className="text-[12px] text-danger">That entity could not be opened.</p>}
          {profile.data && node && (
            <>
              <p className="text-[12px] leading-5 text-muted">
                {plural(profile.data.edges.length, 'link')} · read out of{' '}
                {plural(profile.data.documents.length, 'document')}
              </p>
              {node.sources.length > 0 && (
                <button
                  type="button"
                  onClick={() => void show(node)}
                  className="mt-1.5 inline-flex items-center gap-1.5 text-[12px] text-evidence transition hover:underline"
                >
                  <FileText size={12} />
                  Open the line it came from
                </button>
              )}
              {excerpt && (
                <figure className="mt-2 rounded-lg border border-line bg-evidence-soft px-3 py-2">
                  <figcaption className="text-[11px] uppercase tracking-wide text-subtle">
                    {excerpt.filename}
                  </figcaption>
                  <blockquote className="mt-1 whitespace-pre-wrap text-[12px] leading-6 text-ink">
                    {excerpt.text.trim()}
                  </blockquote>
                </figure>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export function Evidence({ caseId, answer }: { caseId: string; answer: AgentAnswer }) {
  const [open, setOpen] = useState(false)
  const nodes = answer.cited_nodes ?? []
  const edges = answer.cited_edges ?? []

  // Guidance asserts no case fact, so it has nothing to rest on and showing an
  // empty trail under it would read as a failure. §5.3, claim_type.
  if (nodes.length === 0) return null

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        className="text-[12px] text-subtle transition hover:text-evidence"
      >
        {open ? 'Hide what this rests on' : `Rests on ${plural(nodes.length, 'entity', 'entities')}`}
        {edges.length > 0 && !open ? ` and ${plural(edges.length, 'link')}` : ''}
      </button>

      {open && (
        <div className="mt-1.5 rounded-xl border border-line px-3">
          {nodes.map((id) => (
            <Entity key={id} caseId={caseId} nodeId={id} />
          ))}
        </div>
      )}
    </div>
  )
}
