import Foundation
import Observation
import UniformTypeIdentifiers

@MainActor
@Observable
final class AppModel {
    var baseURLString: String {
        didSet { UserDefaults.standard.set(baseURLString, forKey: Self.urlKey) }
    }

    var settings = ClusterSettings()
    var health: HealthResponse?
    var job: Job?
    var errorMessage: String?
    var busy = false
    var pickedPhotoCount = 0
    var zipFileURL: URL?
    var selectedClusterIDs: Set<String> = []
    /// v1 always clusters through clonebins-api. CoreMLIdentityBackend is stubbed only.
    var backend: any IdentityBackend = RemotePythonBackend()

    private var pollTask: Task<Void, Never>?
    private static let urlKey = "clonebins.apiBaseURL"

    init() {
        baseURLString = UserDefaults.standard.string(forKey: Self.urlKey) ?? "http://127.0.0.1:8765"
    }

    var client: CloneBinsAPIClient {
        let trimmed = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        let url = URL(string: trimmed) ?? URL(string: "http://127.0.0.1:8765")!
        return CloneBinsAPIClient(baseURL: url)
    }

    var clustering: Bool { job?.status == .clustering }
    var canExport: Bool { job?.status == .done && !(job?.clusters.isEmpty ?? true) }

    func ping() async {
        do {
            health = try await client.health()
            errorMessage = nil
        } catch {
            health = nil
            errorMessage = error.localizedDescription
        }
    }

    func cluster(files: [UploadFile]) async {
        guard !files.isEmpty else {
            errorMessage = "Pick at least one jpg/png/webp"
            return
        }
        pickedPhotoCount = files.count
        busy = true
        errorMessage = nil
        zipFileURL = nil
        selectedClusterIDs = []
        defer { busy = false }
        do {
            var current = try await client.upload(files)
            current = try await client.startCluster(jobID: current.id, settings: settings)
            job = current
            await pollUntilSettled()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func rename(_ cluster: JobCluster, to name: String) async {
        guard let job else { return }
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, trimmed != cluster.name else { return }
        await mutate {
            try await $0.rename(jobID: job.id, clusterID: cluster.id, name: trimmed)
        }
    }

    func toggleIncluded(_ cluster: JobCluster) async {
        guard let job else { return }
        await mutate {
            try await $0.setIncluded(jobID: job.id, clusterID: cluster.id, included: !cluster.included)
        }
    }

    func mergeSelected() async {
        guard let job, selectedClusterIDs.count >= 2 else { return }
        await mutate {
            try await $0.merge(jobID: job.id, clusterIDs: Array(selectedClusterIDs))
        }
        selectedClusterIDs = []
    }

    func cancel() async {
        guard let job else { return }
        await mutate { try await $0.cancel(jobID: job.id) }
        pollTask?.cancel()
    }

    func prepareZip() async {
        guard let job else { return }
        busy = true
        errorMessage = nil
        defer { busy = false }
        do {
            let data = try await client.downloadZip(jobID: job.id)
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("clonebins.zip")
            try data.write(to: url, options: .atomic)
            zipFileURL = url
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func filesFromURLs(_ urls: [URL]) -> [UploadFile] {
        ImageImport.uploadFiles(from: urls)
    }

    static let importTypes: [UTType] = ImageImport.allowedTypes

    private func pollUntilSettled() async {
        pollTask?.cancel()
        pollTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(300))
                guard let current = self.job, current.status == .clustering else { break }
                do {
                    let next = try await self.client.job(id: current.id)
                    self.job = next
                    if next.status != .clustering { break }
                } catch {
                    self.errorMessage = error.localizedDescription
                    break
                }
            }
        }
        await pollTask?.value
    }

    private func mutate(_ work: (CloneBinsAPIClient) async throws -> Job) async {
        busy = true
        errorMessage = nil
        defer { busy = false }
        do {
            job = try await work(client)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
