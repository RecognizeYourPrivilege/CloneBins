import PhotosUI
import SwiftUI
import UIKit

struct RootView: View {
    @Environment(AppModel.self) private var model
    @State private var photoItems: [PhotosPickerItem] = []
    @State private var showFiles = false
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    privacyBanner
                    connectionBar
                    importBar
                    if let job = model.job {
                        progressBlock(job)
                        ClusterListView(job: job)
                        skippedBlock(job)
                        unmatchedBlock(job)
                    }
                }
                .padding()
            }
            .background(Color(red: 0.09, green: 0.07, blue: 0.05))
            .navigationTitle("CloneBins")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Settings", systemImage: "slider.horizontal.3") { showSettings = true }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    if model.canExport {
                        Button("Zip", systemImage: "square.and.arrow.up") {
                            Task { await model.prepareZip() }
                        }
                        .disabled(model.busy)
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                NavigationStack { SettingsPane() }
                    .environment(model)
                    .presentationDetents([.medium, .large])
            }
            .sheet(isPresented: Binding(
                get: { model.zipFileURL != nil },
                set: { if !$0 { model.zipFileURL = nil } }
            )) {
                if let url = model.zipFileURL {
                    ShareSheet(items: [url])
                }
            }
            .fileImporter(
                isPresented: $showFiles,
                allowedContentTypes: AppModel.importTypes,
                allowsMultipleSelection: true
            ) { result in
                switch result {
                case let .success(urls):
                    Task { await model.cluster(files: model.filesFromURLs(urls)) }
                case let .failure(error):
                    model.errorMessage = error.localizedDescription
                }
            }
            .onChange(of: photoItems) { _, items in
                Task { await importPhotos(items) }
            }
            .task { await model.ping() }
        }
        .preferredColorScheme(.dark)
        .tint(Color(red: 0.85, green: 0.64, blue: 0.25))
    }

    private var privacyBanner: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("LORA DATASET PREP")
                .font(.caption.weight(.semibold))
                .tracking(1.4)
                .foregroundStyle(Color(red: 0.85, green: 0.64, blue: 0.25))
            Text("Processing is on a server you run (this Mac / LAN). No cloud account. On-device Core ML embeddings are not implemented in v1.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(red: 0.13, green: 0.10, blue: 0.08), in: RoundedRectangle(cornerRadius: 14))
    }

    private var connectionBar: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(model.health == nil ? "API unreachable" : "API v\(model.health!.version)")
                Spacer()
                Button("Ping") { Task { await model.ping() } }
            }
            .font(.footnote)
            if let err = model.errorMessage {
                Text(err).font(.footnote).foregroundStyle(.red)
            }
        }
    }

    private var importBar: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("1. Images").font(.headline)
            HStack {
                PhotosPicker(selection: $photoItems, maxSelectionCount: 200, matching: .images) {
                    Label("Photos", systemImage: "photo.on.rectangle")
                }
                .buttonStyle(.borderedProminent)
                Button {
                    showFiles = true
                } label: {
                    Label("Files", systemImage: "folder")
                }
                .buttonStyle(.bordered)
            }
            Text("jpg / png / webp. HEIC from Photos is converted to JPEG on device. Corrupt files are skipped by the API.")
                .font(.caption)
                .foregroundStyle(.secondary)
            if model.pickedPhotoCount > 0 {
                Text("Last import: \(model.pickedPhotoCount) file(s)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if model.busy || model.clustering {
                ProgressView()
            }
            if model.clustering {
                Button("Cancel", role: .destructive) {
                    Task { await model.cancel() }
                }
            }
        }
    }

    @ViewBuilder
    private func progressBlock(_ job: Job) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Job \(job.id) · \(job.status.rawValue) · scanned \(job.scanned)")
                .font(.caption.monospaced())
                .foregroundStyle(.secondary)
            if job.status == .clustering, job.progress.total > 0 {
                ProgressView(value: Double(job.progress.completed), total: Double(max(job.progress.total, 1)))
            }
            ForEach(job.notes, id: \.self) { note in
                Text(note).font(.caption).foregroundStyle(.orange)
            }
        }
    }

    @ViewBuilder
    private func skippedBlock(_ job: Job) -> some View {
        let skipped = job.images.filter(\.skipped)
        if !skipped.isEmpty {
            Text("Skipped: " + skipped.map(\.filename).joined(separator: ", "))
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func unmatchedBlock(_ job: Job) -> some View {
        let unmatched = job.images.filter(\.unmatched)
        if !unmatched.isEmpty {
            Text("Unmatched: " + unmatched.map(\.filename).joined(separator: ", "))
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private func importPhotos(_ items: [PhotosPickerItem]) async {
        guard !items.isEmpty else { return }
        var files: [UploadFile] = []
        for (index, item) in items.enumerated() {
            guard let data = try? await item.loadTransferable(type: Data.self) else { continue }
            if let file = ImageImport.uploadFile(filename: "photo-\(index + 1).jpg", data: data) {
                files.append(file)
            }
        }
        photoItems = []
        await model.cluster(files: files)
    }
}

struct ShareSheet: UIViewControllerRepresentable {
    var items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

#Preview {
    RootView()
        .environment(AppModel())
}
