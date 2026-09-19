import Foundation

struct CloneBinsAPIClient: Sendable {
    var baseURL: URL
    var session: URLSession = .shared

    func health() async throws -> HealthResponse {
        try await get("/api/health")
    }

    func upload(_ files: [UploadFile]) async throws -> Job {
        var request = URLRequest(url: url("/api/jobs/upload"))
        request.httpMethod = "POST"
        request.timeoutInterval = 300
        let boundary = "CloneBins-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = multipartBody(files: files, boundary: boundary)
        return try await send(request)
    }

    func startCluster(jobID: String, settings: ClusterSettings) async throws -> Job {
        try await post("/api/jobs/\(jobID)/cluster", body: settings, timeout: 120)
    }

    func job(id: String) async throws -> Job {
        try await get("/api/jobs/\(id)")
    }

    func cancel(jobID: String) async throws -> Job {
        try await post("/api/jobs/\(jobID)/cancel", body: Empty())
    }

    func rename(jobID: String, clusterID: String, name: String) async throws -> Job {
        try await patch("/api/jobs/\(jobID)/clusters/\(clusterID)", body: ["name": name])
    }

    func setIncluded(jobID: String, clusterID: String, included: Bool) async throws -> Job {
        try await post("/api/jobs/\(jobID)/clusters/\(clusterID)/include", body: ["included": included])
    }

    func merge(jobID: String, clusterIDs: [String]) async throws -> Job {
        try await post("/api/jobs/\(jobID)/merge", body: ["cluster_ids": clusterIDs])
    }

    func exclude(jobID: String, imageIDs: [String]) async throws -> Job {
        try await post("/api/jobs/\(jobID)/exclude", body: ["image_ids": imageIDs])
    }

    func thumbnailURL(jobID: String, imageID: String) -> URL {
        url("/api/jobs/\(jobID)/thumbs/\(imageID)")
    }

    func downloadZip(jobID: String) async throws -> Data {
        var request = URLRequest(url: url("/api/jobs/\(jobID)/export.zip"))
        request.httpMethod = "GET"
        request.timeoutInterval = 300
        let (data, response) = try await session.data(for: request)
        try throwIfNeeded(response, data: data)
        return data
    }

    private struct Empty: Encodable {}

    private func url(_ path: String) -> URL {
        let trimmed = baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        return URL(string: trimmed + path) ?? URL(string: "http://127.0.0.1:8765")!
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: url(path))
        request.httpMethod = "GET"
        request.timeoutInterval = 30
        return try await send(request)
    }

    private func post<Body: Encodable, T: Decodable>(
        _ path: String,
        body: Body,
        timeout: TimeInterval = 60
    ) async throws -> T {
        try await sendJSON(path, method: "POST", body: body, timeout: timeout)
    }

    private func patch<Body: Encodable, T: Decodable>(_ path: String, body: Body) async throws -> T {
        try await sendJSON(path, method: "PATCH", body: body, timeout: 60)
    }

    private func sendJSON<Body: Encodable, T: Decodable>(
        _ path: String,
        method: String,
        body: Body,
        timeout: TimeInterval
    ) async throws -> T {
        var request = URLRequest(url: url(path))
        request.httpMethod = method
        request.timeoutInterval = timeout
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        return try await send(request)
    }

    private func send<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        try throwIfNeeded(response, data: data)
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError(message: "Unexpected API response: \(error.localizedDescription)")
        }
    }

    private func throwIfNeeded(_ response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw APIError(message: "No HTTP response")
        }
        guard (200 ..< 300).contains(http.statusCode) else {
            if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = obj["detail"] as? String
            {
                throw APIError(message: detail)
            }
            throw APIError(message: "HTTP \(http.statusCode)")
        }
    }

    private func multipartBody(files: [UploadFile], boundary: String) -> Data {
        var body = Data()
        let crlf = "\r\n"
        for file in files {
            let safeName = file.filename.replacingOccurrences(of: "\"", with: "_")
            body.append("--\(boundary)\(crlf)")
            body.append("Content-Disposition: form-data; name=\"files\"; filename=\"\(safeName)\"\(crlf)")
            body.append("Content-Type: \(file.mime)\(crlf)\(crlf)")
            body.append(file.data)
            body.append(crlf)
        }
        body.append("--\(boundary)--\(crlf)")
        return body
    }
}

private extension Data {
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) {
            append(data)
        }
    }
}
