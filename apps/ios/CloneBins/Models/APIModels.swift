import Foundation

enum ClusterMode: String, Codable, CaseIterable, Identifiable {
    case face
    case faceBody = "face+body"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .face: "face"
        case .faceBody: "face+body"
        }
    }
}

struct ClusterSettings: Codable, Equatable {
    var threshold: Double = 0.45
    var minImages: Int = 2
    var mode: ClusterMode = .faceBody
    var subjectPrefix: String = "subject"
    var downloadModels: Bool = true
    var keepNames: Bool = true

    enum CodingKeys: String, CodingKey {
        case threshold
        case minImages = "min_images"
        case mode
        case subjectPrefix = "subject_prefix"
        case downloadModels = "download_models"
        case keepNames = "keep_names"
    }
}

struct HealthResponse: Codable, Equatable {
    var ok: Bool
    var version: String
    var privacy: String
    var modelsDir: String
    var modelsReady: Bool

    enum CodingKeys: String, CodingKey {
        case ok, version, privacy
        case modelsDir = "models_dir"
        case modelsReady = "models_ready"
    }
}

enum JobStatus: String, Codable {
    case ready, clustering, done, error, cancelled
}

struct JobProgress: Codable, Equatable {
    var phase: String = ""
    var completed: Int = 0
    var total: Int = 0
    var detail: String = ""
    var logs: [String] = []
}

struct JobImage: Codable, Identifiable, Equatable {
    var id: String
    var filename: String
    var skipped: Bool = false
    var skipReason: String?
    var unmatched: Bool = false
    var unmatchedReason: String?

    enum CodingKeys: String, CodingKey {
        case id, filename, skipped, unmatched
        case skipReason = "skip_reason"
        case unmatchedReason = "unmatched_reason"
    }
}

struct JobCluster: Codable, Identifiable, Equatable {
    var id: String
    var name: String
    var imageIds: [String]
    var included: Bool
    var belowMin: Bool

    enum CodingKeys: String, CodingKey {
        case id, name, included
        case imageIds = "image_ids"
        case belowMin = "below_min"
    }
}

struct Job: Codable, Equatable {
    var id: String
    var status: JobStatus
    var source: String
    var settings: ClusterSettings?
    var progress: JobProgress
    var clusters: [JobCluster]
    var images: [JobImage]
    var notes: [String]
    var backendName: String
    var scanned: Int
    var error: String?

    enum CodingKeys: String, CodingKey {
        case id, status, source, settings, progress, clusters, images, notes, scanned, error
        case backendName = "backend_name"
    }

    var imageById: [String: JobImage] {
        Dictionary(uniqueKeysWithValues: images.map { ($0.id, $0) })
    }
}

struct UploadFile: Identifiable {
    var id = UUID()
    var filename: String
    var data: Data
    var mime: String
}

struct APIError: LocalizedError {
    var message: String
    var errorDescription: String? { message }
}
