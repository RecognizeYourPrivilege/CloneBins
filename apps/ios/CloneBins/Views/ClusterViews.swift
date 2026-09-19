import SwiftUI

struct ClusterListView: View {
    @Environment(AppModel.self) private var model
    var job: Job

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("2. Bins").font(.headline)
                Spacer()
                Button("Merge selected") {
                    Task { await model.mergeSelected() }
                }
                .disabled(model.selectedClusterIDs.count < 2 || model.busy)
            }
            ForEach(job.clusters) { cluster in
                ClusterCard(jobID: job.id, cluster: cluster, images: job.imageById)
            }
        }
    }
}

struct ClusterCard: View {
    @Environment(AppModel.self) private var model
    var jobID: String
    var cluster: JobCluster
    var images: [String: JobImage]
    @State private var draftName: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Button {
                    if model.selectedClusterIDs.contains(cluster.id) {
                        model.selectedClusterIDs.remove(cluster.id)
                    } else {
                        model.selectedClusterIDs.insert(cluster.id)
                    }
                } label: {
                    Image(systemName: model.selectedClusterIDs.contains(cluster.id) ? "checkmark.square.fill" : "square")
                }
                .accessibilityLabel("Select \(cluster.name) for merge")
                TextField("Subject", text: $draftName)
                    .textFieldStyle(.roundedBorder)
                    .onAppear { draftName = cluster.name }
                    .onChange(of: cluster.name) { _, new in draftName = new }
                    .onSubmit {
                        Task { await model.rename(cluster, to: draftName) }
                    }
                Button("Rename") {
                    Task { await model.rename(cluster, to: draftName) }
                }
                .disabled(model.busy)
                Text("\(cluster.imageIds.count)")
                    .font(.caption.monospaced())
                    .foregroundStyle(Color(red: 0.85, green: 0.64, blue: 0.25))
                Toggle("in zip", isOn: Binding(
                    get: { cluster.included },
                    set: { _ in Task { await model.toggleIncluded(cluster) } }
                ))
                .accessibilityLabel("Include \(cluster.name) in zip")
                .labelsHidden()
            }
            if cluster.belowMin {
                Text("Below min-images — off by default. Toggle in zip or merge.")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(cluster.imageIds, id: \.self) { imageID in
                        VStack {
                            AsyncImage(url: model.client.thumbnailURL(jobID: jobID, imageID: imageID)) { phase in
                                switch phase {
                                case let .success(image):
                                    image.resizable().scaledToFill()
                                default:
                                    Color.black.opacity(0.3)
                                }
                            }
                            .frame(width: 88, height: 88)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            Text(images[imageID]?.filename ?? imageID)
                                .font(.caption2)
                                .lineLimit(1)
                                .frame(width: 88)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color(red: 0.13, green: 0.10, blue: 0.08), in: RoundedRectangle(cornerRadius: 14))
        .opacity(cluster.included ? 1 : 0.65)
    }
}
