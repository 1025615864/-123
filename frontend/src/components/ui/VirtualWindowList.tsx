import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'

export interface VirtualWindowListProps<T> {
  items: T[]
  renderItem: (item: T, index: number) => ReactNode
  getItemKey?: (item: T, index: number) => string | number
  estimateItemHeight?: number
  overscan?: number
  className?: string
  itemClassName?: string
}

function binarySearchOffsets(offsets: number[], target: number) {
  let lo = 0
  let hi = Math.max(0, offsets.length - 1)
  while (lo < hi) {
    const mid = Math.floor((lo + hi + 1) / 2)
    if (offsets[mid] <= target) lo = mid
    else hi = mid - 1
  }
  return lo
}

export default function VirtualWindowList<T>({
  items,
  renderItem,
  getItemKey,
  estimateItemHeight = 240,
  overscan = 6,
  className = '',
  itemClassName = '',
}: VirtualWindowListProps<T>) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const sizesRef = useRef<number[]>([])
  const rafRef = useRef<number | null>(null)
  const observersRef = useRef(new Map<number, ResizeObserver>())
  const observedElsRef = useRef(new Map<number, Element>())
  const prevItemsLengthRef = useRef(0)

  const [range, setRange] = useState({ start: 0, end: Math.min(items.length, 20) })
  const [totalHeight, setTotalHeight] = useState(items.length * estimateItemHeight)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const prevLen = prevItemsLengthRef.current
    const prevSizes = sizesRef.current
    const nextSizes = Array.from({ length: items.length }, (_, i) => {
      if (i < prevLen) return prevSizes[i] ?? estimateItemHeight
      return estimateItemHeight
    })

    prevItemsLengthRef.current = items.length
    sizesRef.current = nextSizes
    setTotalHeight(items.length * estimateItemHeight)
    setRange((prev) => {
      const start = Math.min(prev.start, Math.max(0, items.length - 1))
      const end = Math.min(items.length, Math.max(start + 1, prev.end))
      return prev.start === start && prev.end === end ? prev : { start, end }
    })
    setVersion((v) => v + 1)
  }, [estimateItemHeight, items.length])

  const offsets = useMemo(() => {
    const n = items.length
    const next = new Array<number>(n + 1)
    next[0] = 0
    for (let i = 0; i < n; i++) {
      next[i + 1] = next[i] + (sizesRef.current[i] ?? estimateItemHeight)
    }
    return next
  }, [estimateItemHeight, items.length, version])

  useEffect(() => {
    if (items.length === 0) {
      setTotalHeight(0)
      return
    }
    const h = offsets[offsets.length - 1] ?? 0
    setTotalHeight(h)
  }, [items.length, offsets])

  const computeRange = useCallback(() => {
    const container = containerRef.current
    if (!container) return

    const rect = container.getBoundingClientRect()
    const listTop = rect.top + window.scrollY

    const scrollY = window.scrollY
    const viewportHeight = window.innerHeight

    const y0 = Math.max(0, scrollY - listTop)
    const y1 = Math.max(0, scrollY + viewportHeight - listTop)

    const startIndex = Math.min(items.length, binarySearchOffsets(offsets, y0))
    const endIndex = Math.min(items.length, binarySearchOffsets(offsets, y1) + 1)

    const start = Math.max(0, startIndex - overscan)
    const end = Math.min(items.length, endIndex + overscan)

    setRange((prev) => (prev.start === start && prev.end === end ? prev : { start, end }))
  }, [items.length, offsets, overscan])

  useEffect(() => {
    if (items.length === 0) return
    if (rafRef.current != null) return
    rafRef.current = window.requestAnimationFrame(() => {
      rafRef.current = null
      computeRange()
    })
  }, [computeRange, items.length, offsets])

  useEffect(() => {
    const onScrollOrResize = () => {
      if (rafRef.current != null) return
      rafRef.current = window.requestAnimationFrame(() => {
        rafRef.current = null
        computeRange()
      })
    }

    window.addEventListener('scroll', onScrollOrResize, { passive: true })
    window.addEventListener('resize', onScrollOrResize)
    onScrollOrResize()

    return () => {
      window.removeEventListener('scroll', onScrollOrResize)
      window.removeEventListener('resize', onScrollOrResize)
      if (rafRef.current != null) {
        window.cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [computeRange])

  useEffect(() => {
    return () => {
      observersRef.current.forEach((ro) => ro.disconnect())
      observersRef.current.clear()
      observedElsRef.current.clear()
    }
  }, [])

  const registerMeasure = useCallback(
    (index: number) => (el: HTMLDivElement | null) => {
      const prevEl = observedElsRef.current.get(index)
      const prevRo = observersRef.current.get(index)

      if (prevRo) {
        prevRo.disconnect()
        observersRef.current.delete(index)
      }
      if (prevEl) {
        observedElsRef.current.delete(index)
      }

      if (!el) return

      observedElsRef.current.set(index, el)
      const ro = new ResizeObserver(() => {
        const next = el.getBoundingClientRect().height
        const prev = sizesRef.current[index] ?? estimateItemHeight
        if (Math.abs(next - prev) < 1) return
        sizesRef.current[index] = next
        setVersion((v) => v + 1)
      })
      ro.observe(el)
      observersRef.current.set(index, ro)
    },
    [estimateItemHeight]
  )

  const visibleItems = items.slice(range.start, range.end)

  return (
    <div ref={containerRef} className={className} style={{ position: 'relative', height: totalHeight }}>
      {visibleItems.map((item, i) => {
        const index = range.start + i
        const top = offsets[index] ?? 0
        const key = getItemKey ? getItemKey(item, index) : index

        return (
          <div
            key={key}
            ref={registerMeasure(index)}
            className={itemClassName}
            style={{ position: 'absolute', top, left: 0, right: 0 }}
          >
            {renderItem(item, index)}
          </div>
        )
      })}
    </div>
  )
}
