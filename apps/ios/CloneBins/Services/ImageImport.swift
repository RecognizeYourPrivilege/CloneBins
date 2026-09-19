import Foundation
import ImageIO
import UniformTypeIdentifiers

/// Turns Photos / Files bytes into the jpg/png/webp payload `clonebins-api` accepts.
/// HEIC (and other ImageIO-readable types) are transcoded to JPEG on device so the
/// Python OpenCV decoder never sees them.
enum ImageImport {
    static let allowedTypes: [UTType] = [.jpeg, .png, .webP]

    static func uploadFile(filename: String, data: Data) -> UploadFile? {
        if let kind = sniff(data) {
            return UploadFile(
                filename: replacingExtension(filename, with: kind.ext),
                data: data,
                mime: kind.mime
            )
        }
        guard let jpeg = transcodeToJPEG(data) else { return nil }
        return UploadFile(
            filename: replacingExtension(filename, with: "jpg"),
            data: jpeg,
            mime: "image/jpeg"
        )
    }

    static func uploadFiles(from urls: [URL]) -> [UploadFile] {
        urls.compactMap { url in
            let accessed = url.startAccessingSecurityScopedResource()
            defer { if accessed { url.stopAccessingSecurityScopedResource() } }
            guard let data = try? Data(contentsOf: url) else { return nil }
            return uploadFile(filename: url.lastPathComponent, data: data)
        }
    }

    private struct Kind {
        let mime: String
        let ext: String
    }

    private static func sniff(_ data: Data) -> Kind? {
        if data.starts(with: [0xFF, 0xD8, 0xFF]) {
            return Kind(mime: "image/jpeg", ext: "jpg")
        }
        if data.starts(with: [0x89, 0x50, 0x4E, 0x47]) {
            return Kind(mime: "image/png", ext: "png")
        }
        if data.count >= 12 {
            let riff = data.prefix(4)
            let fourCC = data.subdata(in: 8 ..< 12)
            if riff == Data("RIFF".utf8), fourCC == Data("WEBP".utf8) {
                return Kind(mime: "image/webp", ext: "webp")
            }
        }
        return nil
    }

    private static func transcodeToJPEG(_ data: Data) -> Data? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              CGImageSourceGetCount(source) > 0
        else { return nil }
        let destData = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(
            destData,
            UTType.jpeg.identifier as CFString,
            1,
            nil
        ) else { return nil }
        let options: [CFString: Any] = [
            kCGImageDestinationLossyCompressionQuality: 0.92,
        ]
        CGImageDestinationAddImageFromSource(destination, source, 0, options as CFDictionary)
        guard CGImageDestinationFinalize(destination) else { return nil }
        return destData as Data
    }

    private static func replacingExtension(_ filename: String, with ext: String) -> String {
        let stem = URL(fileURLWithPath: filename).deletingPathExtension().lastPathComponent
        let safe = stem.isEmpty ? "image" : stem
        return "\(safe).\(ext)"
    }
}
