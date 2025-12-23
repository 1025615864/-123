declare module 'react-markdown' {
  import type { ComponentType } from 'react'

  const ReactMarkdown: ComponentType<any>
  export default ReactMarkdown
}

declare module 'remark-gfm' {
  const remarkGfm: any
  export default remarkGfm
}
