import Foundation
import PDFKit
import Vision
import AppKit
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let doc = PDFDocument(url: url) else { print("fail"); exit(1) }
for i in 0..<doc.pageCount {
  guard let page = doc.page(at: i) else { continue }
  let rect = page.bounds(for: .mediaBox)
  let scale: CGFloat = 3.0
  let img = page.thumbnail(of: NSSize(width: rect.width*scale, height: rect.height*scale), for: .mediaBox)
  guard let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
  let req = VNRecognizeTextRequest(); req.recognitionLevel = .accurate; req.usesLanguageCorrection = true
  try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
  print("#### PAGE \(i+1)")
  for o in (req.results ?? []) { if let c = o.topCandidates(1).first { print(c.string) } }
}
