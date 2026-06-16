/** 任务完成通知音 */

const AudioContext = window.AudioContext || (window as any).webkitAudioContext

function playTone(frequency: number, duration: number, delay: number = 0) {
  return new Promise<void>((resolve) => {
    setTimeout(() => {
      const ctx = new AudioContext()
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.frequency.value = frequency
      osc.type = 'sine'
      gain.gain.setValueAtTime(0.3, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + duration)
      osc.onended = () => {
        ctx.close()
        resolve()
      }
    }, delay)
  })
}

/** 播放成功提示音（三声上升音） */
export async function playSuccessSound() {
  await playTone(523, 0.15)      // C5
  await playTone(659, 0.15, 150) // E5
  await playTone(784, 0.3, 150)  // G5
}

/** 播放错误提示音（两声下降音） */
export async function playErrorSound() {
  await playTone(400, 0.2)       // 低音
  await playTone(300, 0.4, 200)  // 更低
}

/** 发送系统通知（需用户授权） */
export function sendBrowserNotification(title: string, body: string) {
  if ('Notification' in window) {
    if (Notification.permission === 'granted') {
      new Notification(title, { body, icon: '/favicon.ico' })
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then((perm) => {
        if (perm === 'granted') {
          new Notification(title, { body, icon: '/favicon.ico' })
        }
      })
    }
  }
}
