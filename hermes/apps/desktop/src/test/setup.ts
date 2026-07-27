// jsdom does not currently expose CSS.escape. Desktop code uses the browser
// standard when locating message timeline nodes, so provide the standards
// algorithm for renderer tests instead of weakening production selectors.
if (typeof globalThis.CSS === 'undefined') {
  Object.defineProperty(globalThis, 'CSS', {
    configurable: true,
    value: {}
  })
}

if (typeof globalThis.CSS.escape !== 'function') {
  Object.defineProperty(globalThis.CSS, 'escape', {
    configurable: true,
    value(value: string) {
      const string = String(value)
      const length = string.length
      let result = ''
      const firstCodeUnit = string.charCodeAt(0)

      for (let index = 0; index < length; index += 1) {
        const codeUnit = string.charCodeAt(index)

        if (codeUnit === 0x0000) {
          result += '\uFFFD'

          continue
        }

        if (
          (codeUnit >= 0x0001 && codeUnit <= 0x001f) ||
          codeUnit === 0x007f ||
          (index === 0 && codeUnit >= 0x0030 && codeUnit <= 0x0039) ||
          (index === 1 && codeUnit >= 0x0030 && codeUnit <= 0x0039 && firstCodeUnit === 0x002d)
        ) {
          result += `\\${codeUnit.toString(16)} `

          continue
        }

        if (index === 0 && codeUnit === 0x002d && length === 1) {
          result += `\\${string.charAt(index)}`

          continue
        }

        if (
          codeUnit >= 0x0080 ||
          codeUnit === 0x002d ||
          codeUnit === 0x005f ||
          (codeUnit >= 0x0030 && codeUnit <= 0x0039) ||
          (codeUnit >= 0x0041 && codeUnit <= 0x005a) ||
          (codeUnit >= 0x0061 && codeUnit <= 0x007a)
        ) {
          result += string.charAt(index)

          continue
        }

        result += `\\${string.charAt(index)}`
      }

      return result
    }
  })
}
