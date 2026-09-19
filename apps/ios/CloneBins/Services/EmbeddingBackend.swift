import Foundation

/// Identity embedding source. v1 clustering always runs in `clonebins-api`
/// (`clonebins_core`). Swap `AppModel.backend` later without changing the UI.
protocol IdentityBackend: Sendable {
    var name: String { get }
    var isAvailable: Bool { get }
}

/// Optional on-device path. Not used for clustering in v1.
protocol OnDeviceEmbeddingBackend: IdentityBackend {
    func embed(imageJPEG: Data) async throws -> [Float]
}

/// Default v1 backend: photos are uploaded to a user-run clonebins-api.
struct RemotePythonBackend: IdentityBackend {
    let name = "clonebins-api (Python core)"
    let isAvailable = true
}

/// Placeholder for a later Core ML conversion of YuNet + SFace (or Vision).
/// Not wired into clustering yet — swapping this in should not require a new UI.
struct CoreMLIdentityBackend: OnDeviceEmbeddingBackend {
    let name = "Core ML (not implemented)"
    let isAvailable = false

    func embed(imageJPEG _: Data) async throws -> [Float] {
        throw EmbeddingBackendError.coreMLUnavailable
    }
}

enum EmbeddingBackendError: LocalizedError {
    case coreMLUnavailable

    var errorDescription: String? {
        switch self {
        case .coreMLUnavailable:
            "On-device Core ML embeddings are not implemented in v1. Point the app at clonebins-api on your Mac or LAN."
        }
    }
}
