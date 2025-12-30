import { test, expect } from '@playwright/test'

test('前台：Chat 语音输入可转写并回填到输入框（mock）', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('guest_ai_used')
    localStorage.removeItem('guest_ai_reset_at')

    ;(navigator as any).mediaDevices = (navigator as any).mediaDevices ?? {}
    ;(navigator as any).mediaDevices.getUserMedia = async () => {
      return {
        getTracks: () => [
          {
            stop: () => {},
          },
        ],
      }
    }

    class FakeMediaRecorder {
      public mimeType = 'audio/webm'
      public ondataavailable: ((evt: any) => void) | null = null
      public onstop: (() => void) | null = null
      constructor(_stream: any) {
        _stream
      }
      start() {
        return
      }
      stop() {
        const blob = new Blob([new Uint8Array([1, 2, 3])], { type: this.mimeType })
        this.ondataavailable?.({ data: blob })
        this.onstop?.()
      }
    }

    ;(window as any).MediaRecorder = FakeMediaRecorder
  })

  let hitTranscribe = false
  await page.route('**/api/ai/transcribe', async (route) => {
    hitTranscribe = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ text: '转写结果：你好' }),
    })
  })

  await page.goto('/chat')

  const startBtn = page.getByRole('button', { name: '语音输入' })
  await expect(startBtn).toBeVisible({ timeout: 12_000 })
  await startBtn.click()

  const stopBtn = page.getByRole('button', { name: '停止录音' })
  await expect(stopBtn).toBeVisible({ timeout: 12_000 })
  await stopBtn.click()

  await expect.poll(() => hitTranscribe).toBeTruthy()

  const input = page.getByPlaceholder('输入您的法律问题...')
  await expect(input).toHaveValue('转写结果：你好')
})
