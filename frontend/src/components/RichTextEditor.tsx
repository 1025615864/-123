import { useState, useRef, useCallback } from 'react'
import { Image, Link, Smile, Bold, Italic, List, X, Upload, Paperclip } from 'lucide-react'
import { Button, FadeInImage } from './ui'
import api from '../api/client'
import { useToast } from '../hooks'
import { getApiErrorMessage } from '../utils'

// 常用表情列表
const EMOJI_LIST = [
  '😀', '😃', '😄', '😁', '😅', '😂', '🤣', '😊', '😇', '🙂',
  '😉', '😍', '🥰', '😘', '😗', '😋', '😛', '🤔', '🤨', '😐',
  '😑', '😶', '😏', '😒', '🙄', '😬', '😮', '😯', '😲', '😳',
  '🥺', '😢', '😭', '😤', '😡', '🤬', '😈', '👿', '💀', '☠️',
  '👍', '👎', '👏', '🙌', '🤝', '🙏', '✌️', '🤞', '🤟', '🤙',
  '💪', '🦾', '🖕', '✍️', '🤳', '💅', '🦵', '🦶', '👂', '👃',
  '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💔',
  '💯', '💢', '💥', '💫', '💦', '💨', '🕳️', '💣', '💬', '👋',
]

interface RichTextEditorProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  images?: string[]
  onImagesChange?: (images: string[]) => void
  attachments?: Array<{ name: string; url: string }>
  onAttachmentsChange?: (attachments: Array<{ name: string; url: string }>) => void
  minHeight?: string
}

export default function RichTextEditor({
  value,
  onChange,
  placeholder = '请输入内容...',
  images = [],
  onImagesChange,
  attachments = [],
  onAttachmentsChange,
  minHeight = '200px',
}: RichTextEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const attachmentInputRef = useRef<HTMLInputElement>(null)
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [showLinkInput, setShowLinkInput] = useState(false)
  const [linkUrl, setLinkUrl] = useState('')
  const [linkText, setLinkText] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadingAttachment, setUploadingAttachment] = useState(false)
  const toast = useToast()

  // 插入文本到光标位置
  const insertText = useCallback((text: string) => {
    const textarea = textareaRef.current
    if (!textarea) return

    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const newValue = value.substring(0, start) + text + value.substring(end)
    onChange(newValue)

    // 设置光标位置
    setTimeout(() => {
      textarea.focus()
      textarea.setSelectionRange(start + text.length, start + text.length)
    }, 0)
  }, [value, onChange])

  // 插入表情
  const insertEmoji = (emoji: string) => {
    insertText(emoji)
    setShowEmojiPicker(false)
  }

  // 插入链接
  const insertLink = () => {
    if (!linkUrl.trim()) return
    const text = linkText.trim() || linkUrl
    const markdown = `[${text}](${linkUrl})`
    insertText(markdown)
    setShowLinkInput(false)
    setLinkUrl('')
    setLinkText('')
  }

  // 包裹选中文本
  const wrapSelection = (prefix: string, suffix: string) => {
    const textarea = textareaRef.current
    if (!textarea) return

    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const selectedText = value.substring(start, end)
    const newText = prefix + selectedText + suffix
    const newValue = value.substring(0, start) + newText + value.substring(end)
    onChange(newValue)

    setTimeout(() => {
      textarea.focus()
      textarea.setSelectionRange(start + prefix.length, start + prefix.length + selectedText.length)
    }, 0)
  }

  // 处理图片上传
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || !onImagesChange) return

    setUploading(true)
    try {
      const uploadedUrls: string[] = []
      for (const file of Array.from(files)) {
        if (!file.type.startsWith('image/')) continue
        const formData = new FormData()
        formData.append('file', file)
        const res = await api.post('/upload/image', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        if (res.data?.url) {
          uploadedUrls.push(res.data.url)
        }
      }

      if (uploadedUrls.length > 0) {
        onImagesChange([...images, ...uploadedUrls])
        const md = uploadedUrls.map((url) => `![](${url})`).join('\n')
        insertText(`\n\n${md}\n\n`)
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, '上传失败，请稍后重试'))
    } finally {
      setUploading(false)
      // 清空input以允许重复选择同一文件
      e.target.value = ''
    }
  }

  const handleAttachmentUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || !onAttachmentsChange) return

    setUploadingAttachment(true)
    try {
      const uploaded: Array<{ name: string; url: string }> = []
      for (const file of Array.from(files)) {
        const formData = new FormData()
        formData.append('file', file)
        const res = await api.post('/upload/file', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        const url = res.data?.url
        const name = res.data?.original_name || file.name
        if (typeof url === 'string' && url) {
          uploaded.push({ name: String(name || '附件'), url })
        }
      }

      if (uploaded.length > 0) {
        onAttachmentsChange([...attachments, ...uploaded])
        const md = uploaded.map((att) => `[${att.name}](${att.url})`).join('\n')
        insertText(`\n\n${md}\n\n`)
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, '上传失败，请稍后重试'))
    } finally {
      setUploadingAttachment(false)
      e.target.value = ''
    }
  }

  // 删除图片
  const removeImage = (index: number) => {
    if (!onImagesChange) return
    const newImages = images.filter((_, i) => i !== index)
    onImagesChange(newImages)
  }

  return (
    <div className="rounded-xl border border-slate-200/70 bg-white overflow-hidden dark:border-white/10 dark:bg-[#0f0a1e]/60">
      {/* 工具栏 */}
      <div className="flex items-center gap-1 p-2 border-b border-slate-200/70 bg-slate-50 dark:border-white/10 dark:bg-white/5">
        <button
          type="button"
          onClick={() => wrapSelection('**', '**')}
          className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-900/5 transition-colors dark:text-white/60 dark:hover:text-white dark:hover:bg-white/10"
          title="加粗"
        >
          <Bold className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => wrapSelection('*', '*')}
          className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-900/5 transition-colors dark:text-white/60 dark:hover:text-white dark:hover:bg-white/10"
          title="斜体"
        >
          <Italic className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => insertText('\n- ')}
          className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-900/5 transition-colors dark:text-white/60 dark:hover:text-white dark:hover:bg-white/10"
          title="列表"
        >
          <List className="h-4 w-4" />
        </button>
        
        <div className="w-px h-5 bg-slate-200 mx-1 dark:bg-white/10" />
        
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowEmojiPicker(!showEmojiPicker)}
            className={`p-2 rounded-lg transition-colors ${
              showEmojiPicker
                ? 'text-amber-700 bg-amber-500/15 dark:text-amber-400 dark:bg-amber-500/20'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-900/5 dark:text-white/60 dark:hover:text-white dark:hover:bg-white/10'
            }`}
            title="表情"
          >
            <Smile className="h-4 w-4" />
          </button>
          
          {showEmojiPicker && (
            <div className="absolute top-full left-0 mt-1 p-3 bg-white border border-slate-200/70 rounded-xl shadow-xl z-50 w-[320px] dark:bg-[#1a1128] dark:border-white/10">
              <div className="grid grid-cols-10 gap-1 max-h-[200px] overflow-y-auto">
                {EMOJI_LIST.map((emoji, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => insertEmoji(emoji)}
                    className="p-1.5 text-lg hover:bg-slate-900/5 rounded transition-colors dark:hover:bg-white/10"
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowLinkInput(!showLinkInput)}
            className={`p-2 rounded-lg transition-colors ${
              showLinkInput
                ? 'text-amber-700 bg-amber-500/15 dark:text-amber-400 dark:bg-amber-500/20'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-900/5 dark:text-white/60 dark:hover:text-white dark:hover:bg-white/10'
            }`}
            title="插入链接"
          >
            <Link className="h-4 w-4" />
          </button>
          
          {showLinkInput && (
            <div className="absolute top-full left-0 mt-1 p-3 bg-white border border-slate-200/70 rounded-xl shadow-xl z-50 w-[280px] dark:bg-[#1a1128] dark:border-white/10">
              <div className="space-y-3">
                <input
                  type="text"
                  value={linkText}
                  onChange={(e) => setLinkText(e.target.value)}
                  placeholder="链接文字（可选）"
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200/70 bg-white text-slate-900 placeholder:text-slate-400 outline-none dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder:text-white/30"
                />
                <input
                  type="url"
                  value={linkUrl}
                  onChange={(e) => setLinkUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200/70 bg-white text-slate-900 placeholder:text-slate-400 outline-none dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder:text-white/30"
                />
                <div className="flex justify-end gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setShowLinkInput(false)}>
                    取消
                  </Button>
                  <Button size="sm" onClick={insertLink} disabled={!linkUrl.trim()}>
                    插入
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
        
        {onImagesChange && (
          <>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-900/5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed dark:text-white/60 dark:hover:text-white dark:hover:bg-white/10"
              title="上传图片"
            >
              <Image className="h-4 w-4" />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={handleImageUpload}
              className="hidden"
            />
          </>
        )}

        {onAttachmentsChange ? (
          <>
            <button
              type="button"
              onClick={() => attachmentInputRef.current?.click()}
              disabled={uploadingAttachment}
              className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-900/5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed dark:text-white/60 dark:hover:text-white dark:hover:bg-white/10"
              title="上传附件"
            >
              <Paperclip className="h-4 w-4" />
            </button>
            <input
              ref={attachmentInputRef}
              type="file"
              multiple
              onChange={handleAttachmentUpload}
              className="hidden"
            />
          </>
        ) : null}
      </div>

      {/* 文本区域 */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{ minHeight }}
        className="w-full px-4 py-3 bg-transparent text-slate-900 placeholder:text-slate-400 outline-none resize-y dark:text-white dark:placeholder:text-white/30"
      />

      {/* 图片预览 */}
      {images.length > 0 && (
        <div className="p-3 border-t border-slate-200/70 dark:border-white/10">
          <div className="flex flex-wrap gap-2">
            {images.map((img, index) => (
              <div key={index} className="relative group">
                <FadeInImage
                  src={img}
                  alt={`预览 ${index + 1}`}
                  wrapperClassName="w-20 h-20 rounded-lg"
                  className="h-full w-full object-cover"
                />
                <button
                  type="button"
                  onClick={() => removeImage(index)}
                  className="absolute -top-2 -right-2 p-1 bg-red-500 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="w-20 h-20 rounded-lg border-2 border-dashed border-slate-300 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-400 transition-colors disabled:opacity-60 disabled:cursor-not-allowed dark:border-white/20 dark:text-white/40 dark:hover:text-white/60 dark:hover:border-white/40"
            >
              <Upload className="h-6 w-6" />
            </button>
          </div>
          <p className="text-xs text-slate-500 mt-2 dark:text-white/40">已添加 {images.length} 张图片</p>
        </div>
      )}

      {/* 点击外部关闭弹出框 */}
      {(showEmojiPicker || showLinkInput) && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => {
            setShowEmojiPicker(false)
            setShowLinkInput(false)
          }}
        />
      )}
    </div>
  )
}
