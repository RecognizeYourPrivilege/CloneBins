import SwiftUI

struct SettingsPane: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        @Bindable var model = model
        Form {
            Section("Server") {
                TextField("API base URL", text: $model.baseURLString)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                    .accessibilityLabel("API base URL")
                Text("Simulator: http://127.0.0.1:8765 while clonebins-api runs on this Mac. Physical device: http://<Mac-LAN-IP>:8765 and start the API with CLONEBINS_API_HOST=0.0.0.0 so it listens on the LAN. Not a cloud service.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                Button("Check connection") { Task { await model.ping() } }
                if let health = model.health {
                    LabeledContent("API", value: "v\(health.version)")
                    LabeledContent("Models", value: health.modelsReady ? "ready" : "missing (appearance fallback)")
                } else {
                    Text("API unreachable — import/cluster will fail until Ping succeeds.")
                        .font(.footnote)
                        .foregroundStyle(.red)
                }
            }
            Section("Clustering") {
                Picker("Mode", selection: $model.settings.mode) {
                    ForEach(ClusterMode.allCases) { mode in
                        Text(mode.label).tag(mode)
                    }
                }
                VStack(alignment: .leading) {
                    Text("Similarity threshold \(model.settings.threshold, specifier: "%.2f")")
                    Slider(value: $model.settings.threshold, in: 0.15 ... 0.90, step: 0.01)
                }
                Stepper("Min images per bin: \(model.settings.minImages)", value: $model.settings.minImages, in: 1 ... 50)
                TextField("Subject prefix", text: $model.settings.subjectPrefix)
                    .textInputAutocapitalization(.never)
                Toggle("Keep original filenames in zip", isOn: $model.settings.keepNames)
                Toggle("Download face models if missing (on the API host)", isOn: $model.settings.downloadModels)
            }
            Section("Identity backend") {
                LabeledContent("Active", value: model.backend.name)
                LabeledContent("Core ML", value: CoreMLIdentityBackend().isAvailable ? "ready" : "future work")
                Text("v1 always clusters through clonebins-api / clonebins_core. OnDeviceEmbeddingBackend / CoreMLIdentityBackend are stubbed for an on-device YuNet+SFace (or Vision) path later — the UI does not need to change.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Settings")
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("Done") { dismiss() }
            }
        }
    }
}
